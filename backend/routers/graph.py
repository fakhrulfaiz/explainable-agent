from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from uuid import uuid4
from datetime import datetime
from typing import Annotated
import logging
import json
import asyncio

from src.models.schemas import StartRequest, GraphResponse, GraphStatusResponse, ResumeRequest
from src.models.status_enums import ExecutionStatus, ApprovalStatus
from src.services.explainable_agent import ExplainableAgent, ExplainableAgentState
from langchain_core.messages import HumanMessage
from src.models.database import get_mongo_memory, get_mongodb

router = APIRouter(
    prefix="/graph",
    tags=["graph"]
)

# Dependency functions that access app state
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent


def run_graph_and_response(explainable_agent: ExplainableAgent, input_state, config):
    logger = logging.getLogger(__name__)
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    # Initialize query variable with default value to avoid scoping issues
    query = ""
    
    operation = "resume" if input_state is None else "start"
    input_state_str = 'None' if input_state is None else 'provided'
    logger.info(f"Graph execution ({operation}) for thread_id: {thread_id}, input_state: {input_state_str}")
    
    try:
        # Use streaming instead of invoke
        if input_state is None:
            # Resume case - continue from current state
            events = list(explainable_agent.graph.stream(None, config, stream_mode="values"))
        else:
            # Start case - stream with initial state
            events = list(explainable_agent.graph.stream(input_state, config, stream_mode="values"))
        
        # Get the final state after streaming
        state = explainable_agent.graph.get_state(config)
        next_nodes = state.next
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = None
        query = state.values.get("query", "")
        if hasattr(state, 'config') and state.config and 'configurable' in state.config:
            configurable = state.config['configurable']
            if 'checkpoint_id' in configurable:
                checkpoint_id = str(configurable['checkpoint_id'])
            
        
        if next_nodes and "human_feedback" in next_nodes:
            execution_status = ExecutionStatus.USER_FEEDBACK
            # Get the plan from current state for user review
            current_values = state.values
            
            assistant_response = current_values.get("assistant_response") or current_values.get("plan", "Plan generated - awaiting approval")
            plan = current_values.get("plan", "")
            response_type = current_values.get("response_type")  # Get response_type from state
            
            return GraphResponse(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                query=query,
                run_status=execution_status, 
                assistant_response=assistant_response,
                plan=plan,
                response_type=response_type  # Include response_type in response
            )
        else:
            execution_status = ExecutionStatus.FINISHED
            
            # Extract the response from the final state
            final_values = state.values
            messages = final_values.get("messages", [])
            
            # Get the last AI message as the assistant response
            assistant_response = ""
            for msg in reversed(messages):
                if (hasattr(msg, 'content') and msg.content and 
                    type(msg).__name__ == 'AIMessage' and
                    (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                    assistant_response = msg.content
                    break
            
            if not assistant_response and events:
                final_event = events[-1]
                if isinstance(final_event, dict) and "messages" in final_event:
                    event_messages = final_event["messages"]
                    for msg in reversed(event_messages):
                        if (hasattr(msg, 'content') and msg.content and 
                            type(msg).__name__ == 'AIMessage' and
                            (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                            assistant_response = msg.content
                            break
        
            steps = final_values.get("steps", [])
            plan = final_values.get("plan", "")
            
            total_time = None
            overall_confidence = None
            final_result = None
            
            if steps:
                # Calculate overall confidence
                confidences = [step.get("confidence", 0.8) for step in steps if "confidence" in step]
                overall_confidence = sum(confidences) / len(confidences) if confidences else 0.8
                
                 
                from src.models.schemas import FinalResult
                final_result = FinalResult(
                    summary=assistant_response,
                    details=f"Executed {len(steps)} steps successfully",
                    source="Database query execution",
                    inference="Based on database analysis and tool execution",
                    extra_explanation=f"Plan: {plan}"
                )
            
            return GraphResponse(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                query=query,
                run_status=execution_status,
                assistant_response=assistant_response,
                plan=plan,
                steps=steps,
                final_result=final_result,
                total_time=total_time,
                overall_confidence=overall_confidence
            )
            
    except Exception as e:
        error_message = str(e) if e else "Unknown error occurred"
        logger.error(f"Graph execution failed for thread_id: {thread_id}, error: {error_message}")
        return GraphResponse(
            thread_id=thread_id,
            checkpoint_id=None,  # No checkpoint_id available on error
            query=query,
            run_status="error",
            error=error_message
        )


@router.post("/start", response_model=GraphResponse)
def start_graph(
    request: StartRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    try:
        # Use provided thread_id or generate new one
        thread_id = request.thread_id or str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}
         
        
        initial_state = ExplainableAgentState(
            messages=[HumanMessage(content=request.human_request)],
            query=request.human_request,
            plan="",
            steps=[],
            step_counter=0,
            status="approved",
            assistant_response="",
            use_planning=request.use_planning,  # Set planning preference from API
            agent_type="data_exploration_agent",  # Skip assistant node, go directly to data exploration
            routing_reason="Direct routing to data exploration agent"  # Skip assistant node
        )
        
        
        return run_graph_and_response(agent, initial_state, config)
    except Exception as e:
        return GraphResponse(
            thread_id=thread_id if 'thread_id' in locals() else "unknown",
            run_status="error",
            error=f"Failed to start graph: {str(e)}"
        )


@router.post("/resume", response_model=GraphResponse)
def resume_graph(
    request: ResumeRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    logger = logging.getLogger(__name__)
    config = {"configurable": {"thread_id": request.thread_id}}
    
    logger.info(f"Resuming graph for thread_id: {request.thread_id}, action: {request.review_action}")
    
    try:
        # Get current state
        current_state = agent.graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail=f"No graph execution found for thread_id: {request.thread_id}")
        
        # Check if the graph is already running (not waiting for feedback)
        if not (current_state.next and "human_feedback" in current_state.next):
            logger.warning(f"Thread {request.thread_id} is not waiting for human feedback. Current next nodes: {current_state.next}")
            raise HTTPException(status_code=400, detail=f"Graph execution for thread_id {request.thread_id} is not waiting for human feedback")
        
        state_update = {"status": request.review_action}
        if request.human_comment is not None:
            state_update["human_comment"] = request.human_comment
        
        logger.info(f"State to update for thread {request.thread_id}: {state_update}")
        
        agent.graph.update_state(config, state_update)
        
        # Continue execution
        return run_graph_and_response(agent, None, config)
        
    except Exception as e:
        error_message = str(e) if e else "Unknown error occurred"
        if "thread_id" in error_message.lower() or "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=f"Graph execution not found for thread_id: {request.thread_id}")
        raise HTTPException(status_code=500, detail=f"Error resuming graph: {error_message}")


@router.get("/status/{thread_id}", response_model=GraphStatusResponse)
def get_graph_status(
    thread_id: str,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
  
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state = agent.graph.get_state(config)
        if not state:
            raise HTTPException(status_code=404, detail=f"No graph execution found for thread_id: {thread_id}")
        
        next_nodes = state.next
        values = state.values
        
        if next_nodes and "human_feedback" in next_nodes:
            execution_status = ExecutionStatus.USER_FEEDBACK
        elif next_nodes:
            execution_status = ExecutionStatus.RUNNING
        else:
            execution_status = ExecutionStatus.FINISHED
        
        return GraphStatusResponse(
            thread_id=thread_id,
            execution_status=execution_status,  # Graph execution state
            next_nodes=list(next_nodes) if next_nodes else [],
            plan=values.get("plan", ""),
            step_count=len(values.get("steps", [])),
            approval_status=values.get("status", ApprovalStatus.UNKNOWN)  # Agent approval state
        )
        
    except Exception as e:
        if "thread_id" in str(e).lower() or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Graph execution not found for thread_id: {thread_id}")
        raise HTTPException(status_code=500, detail=f"Error getting graph status: {str(e)}")



@router.get("/state/{thread_id}/agent")
def get_agent_state_via_agent(
    thread_id: str,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    """
    Fetch the agent's current state via the compiled graph.
    If thread exists in MongoDB but not loaded in agent, it will load it first.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        # Try to get current state from agent
        state = agent.graph.get_state(config)
        
        # If no state found in agent memory, but checkpoints exist in MongoDB,
        # the agent will automatically load from the checkpointer
        if not state or not hasattr(state, 'values') or not state.values:
            # Force a checkpoint load by trying to get state again
            # The MongoDBSaver should automatically restore from DB
            state = agent.graph.get_state(config)
        
        if not state or not hasattr(state, 'values') or not state.values:
            raise HTTPException(status_code=404, detail=f"No graph execution found for thread_id: {thread_id}")
        
        values = getattr(state, "values", {}) or {}
        next_nodes = getattr(state, "next", None)
        
        # Check if this is a loaded state vs empty state
        has_meaningful_data = (
            values.get("messages") or 
            values.get("plan") or 
            values.get("query") or
            values.get("steps")
        )
        
        if not has_meaningful_data:
            raise HTTPException(status_code=404, detail=f"No meaningful state found for thread_id: {thread_id}")
        
        # Summarize values to avoid returning non-serializable objects
        summary = {
            "thread_id": thread_id,
            "has_state": True,
            "next_nodes": list(next_nodes) if next_nodes else [],
            "values": {
                "messages_count": len(values.get("messages", [])) if isinstance(values.get("messages"), list) else 0,
                "steps_count": len(values.get("steps", [])) if isinstance(values.get("steps"), list) else 0,
                "plan": values.get("plan", ""),
                "query": values.get("query", ""),
                "approval_status": values.get("status", "unknown"),
                "step_counter": values.get("step_counter", 0),
                "has_human_comment": bool(values.get("human_comment")),
                "assistant_response": values.get("assistant_response", "")
            },
            "source": "agent.graph.get_state",
            "loaded_from_checkpoint": True
        }
        return summary
    except HTTPException:
        raise 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching agent state via agent: {str(e)}")


@router.post("/state/{thread_id}/restore")
def restore_agent_state(
    thread_id: str,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    """
    Explicitly restore/load a thread's state from MongoDB checkpointer into the agent.
    Useful after server restart to ensure the agent has the latest state.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        # Force load from checkpointer by getting state
        state = agent.graph.get_state(config)
        
        if not state or not hasattr(state, 'values') or not state.values:
            raise HTTPException(status_code=404, detail=f"No checkpoint found for thread_id: {thread_id}")
        
        values = state.values
        next_nodes = state.next
        
        return {
            "thread_id": thread_id,
            "operation_status": "restored",
            "has_state": True,
            "next_nodes": list(next_nodes) if next_nodes else [],
            "restored_data": {
                "messages_count": len(values.get("messages", [])) if isinstance(values.get("messages"), list) else 0,
                "steps_count": len(values.get("steps", [])) if isinstance(values.get("steps"), list) else 0,
                "plan": values.get("plan", ""),
                "query": values.get("query", ""),
                "approval_status": values.get("status", "unknown"),
                "step_counter": values.get("step_counter", 0)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring agent state: {str(e)}")


# Streaming endpoints for real-time updates
def yield_sse_event(event_type: str, data: dict) -> str:
    """Helper function to create properly formatted SSE events"""
    event_data = {
        "type": event_type,
        "data": data
    }
    # Ensure proper JSON formatting with no trailing spaces
    json_str = json.dumps(event_data, ensure_ascii=False, separators=(',', ':'))
    return f"data: {json_str}\n\n"


@router.post("/start/stream")
async def start_graph_stream(
    request: StartRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    """
    Start graph execution with real-time streaming of internal AI messages and progress.
    Returns Server-Sent Events (SSE) stream.
    """
    async def event_generator():
        thread_id = None
        try:
            # Use provided thread_id or generate new one
            thread_id = request.thread_id or str(uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            
            initial_state = ExplainableAgentState(
                messages=[HumanMessage(content=request.human_request)],
                query=request.human_request,
                plan="",
                steps=[],
                step_counter=0,
                status="approved",
                assistant_response="",
                use_planning=request.use_planning,
                agent_type="data_exploration_agent",
                routing_reason=""
            )
            
            # Send initial status
            yield yield_sse_event("status", {
                "thread_id": thread_id,
                "status": "starting",
                "message": "Initializing graph execution..."
            })
            
            await asyncio.sleep(0.1)  # Small delay for client connection
            
            # Convert sync stream to async
            def sync_stream():
                return agent.graph.stream(initial_state, config, stream_mode="values")
            
            # Stream events as they happen
            for event in sync_stream():
                # Send internal AI messages/reasoning
                if "messages" in event and event["messages"]:
                    latest_message = event["messages"][-1]
                    if latest_message and hasattr(latest_message, 'content') and latest_message.content:
                        if type(latest_message).__name__ == 'AIMessage':
                            # Check if it's a reasoning message (not a tool call response)
                            if not hasattr(latest_message, 'tool_calls') or not latest_message.tool_calls:
                                # Truncate very long content to prevent JSON parsing issues
                                content = latest_message.content
                                if len(content) > 10000:  # Limit to 10KB
                                    content = content[:10000] + "... [truncated]"
                                
                                yield yield_sse_event("ai_thinking", {
                                    "content": content,
                                    "temporary": True,
                                    "timestamp": datetime.now().isoformat()
                                })
                
                # Send plan updates
                if "plan" in event and event["plan"]:
                    yield yield_sse_event("plan_update", {
                        "plan": event["plan"],
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Send step progress updates
                if "steps" in event and event["steps"]:
                    step_count = len(event["steps"])
                    latest_step = event["steps"][-1] if event["steps"] else None
                    yield yield_sse_event("step_progress", {
                        "completed_steps": step_count,
                        "latest_step": latest_step,
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Send assistant response updates
                if "assistant_response" in event and event["assistant_response"]:
                    yield yield_sse_event("assistant_response", {
                        "response": event["assistant_response"],
                        "timestamp": datetime.now().isoformat()
                    })
                
                await asyncio.sleep(0.05)  # Small delay between events
            
            # Get final state and determine completion status
            final_state = agent.graph.get_state(config)
            
            if final_state.next and "human_feedback" in final_state.next:
                # Waiting for user feedback
                current_values = final_state.values
                assistant_response = current_values.get("assistant_response") or current_values.get("plan", "Plan generated - awaiting approval")
                response_type = current_values.get("response_type")  # Get response_type from state
                
                yield yield_sse_event("waiting_feedback", {
                    "status": "user_feedback",
                    "thread_id": thread_id,
                    "plan": current_values.get("plan", ""),
                    "assistant_response": assistant_response,
                    "response_type": response_type,  # Include response_type
                    "timestamp": datetime.now().isoformat()
                })
            else:
                # Execution completed
                final_values = final_state.values
                messages = final_values.get("messages", [])
                
                # Get the last AI message as the final response
                final_response = ""
                for msg in reversed(messages):
                    if (hasattr(msg, 'content') and msg.content and 
                        type(msg).__name__ == 'AIMessage' and
                        (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                        final_response = msg.content
                        break
                
                yield yield_sse_event("completed", {
                    "status": "finished",
                    "thread_id": thread_id,
                    "final_response": final_response,
                    "steps": final_values.get("steps", []),
                    "plan": final_values.get("plan", ""),
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            error_message = str(e)
            yield yield_sse_event("error", {
                "error": error_message,
                "thread_id": thread_id,
                "timestamp": datetime.now().isoformat()
            })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )


@router.post("/resume/stream")
async def resume_graph_stream(
    request: ResumeRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    """
    Resume graph execution with real-time streaming of internal AI messages and progress.
    Returns Server-Sent Events (SSE) stream.
    """
    async def event_generator():
        logger = logging.getLogger(__name__)
        try:
            config = {"configurable": {"thread_id": request.thread_id}}
            
            logger.info(f"Resuming graph stream for thread_id: {request.thread_id}, action: {request.review_action}")
            
            # Get current state to validate
            current_state = agent.graph.get_state(config)
            if not current_state:
                yield yield_sse_event("error", {
                    "error": f"No graph execution found for thread_id: {request.thread_id}",
                    "thread_id": request.thread_id,
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # Check if waiting for feedback
            if not (current_state.next and "human_feedback" in current_state.next):
                yield yield_sse_event("error", {
                    "error": f"Graph execution for thread_id {request.thread_id} is not waiting for human feedback",
                    "thread_id": request.thread_id,
                    "current_next_nodes": list(current_state.next) if current_state.next else [],
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # Send resume status
            yield yield_sse_event("status", {
                "thread_id": request.thread_id,
                "status": "resuming",
                "action": request.review_action,
                "message": f"Resuming execution with action: {request.review_action}"
            })
            
            # Update state with user decision
            state_update = {"status": request.review_action}
            if request.human_comment is not None:
                state_update["human_comment"] = request.human_comment
            
            logger.info(f"State update for thread {request.thread_id}: {state_update}")
            agent.graph.update_state(config, state_update)
            
            await asyncio.sleep(0.1)  # Small delay after state update
            
            # Convert sync stream to async for continuation
            def sync_resume_stream():
                return agent.graph.stream(None, config, stream_mode="values")
            
            # Stream continuation events with same logic as start
            for event in sync_resume_stream():
                # Send internal AI messages/reasoning
                if "messages" in event and event["messages"]:
                    latest_message = event["messages"][-1]
                    if latest_message and hasattr(latest_message, 'content') and latest_message.content:
                        if type(latest_message).__name__ == 'AIMessage':
                            if not hasattr(latest_message, 'tool_calls') or not latest_message.tool_calls:
                                yield yield_sse_event("ai_thinking", {
                                    "content": latest_message.content,
                                    "temporary": True,
                                    "timestamp": datetime.now().isoformat()
                                })
                
                # Send step progress
                if "steps" in event and event["steps"]:
                    step_count = len(event["steps"])
                    latest_step = event["steps"][-1] if event["steps"] else None
                    yield yield_sse_event("step_progress", {
                        "completed_steps": step_count,
                        "latest_step": latest_step,
                        "timestamp": datetime.now().isoformat()
                    })
                
                await asyncio.sleep(0.05)
            
            # Get final state
            final_state = agent.graph.get_state(config)
            
            if final_state.next and "human_feedback" in final_state.next:
                # Still waiting for more feedback
                current_values = final_state.values
                response_type = current_values.get("response_type")  # Get response_type from state
                yield yield_sse_event("waiting_feedback", {
                    "status": "user_feedback",
                    "thread_id": request.thread_id,
                    "plan": current_values.get("plan", ""),
                    "assistant_response": current_values.get("assistant_response", ""),
                    "response_type": response_type,  # Include response_type
                    "timestamp": datetime.now().isoformat()
                })
            else:
                # Execution completed
                final_values = final_state.values
                messages = final_values.get("messages", [])
                
                final_response = ""
                for msg in reversed(messages):
                    if (hasattr(msg, 'content') and msg.content and 
                        type(msg).__name__ == 'AIMessage' and
                        (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                        final_response = msg.content
                        break
                
                yield yield_sse_event("completed", {
                    "status": "finished",
                    "thread_id": request.thread_id,
                    "final_response": final_response,
                    "steps": final_values.get("steps", []),
                    "plan": final_values.get("plan", ""),
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in resume stream for thread {request.thread_id}: {error_message}")
            yield yield_sse_event("error", {
                "error": error_message,
                "thread_id": request.thread_id,
                "timestamp": datetime.now().isoformat()
            })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )
