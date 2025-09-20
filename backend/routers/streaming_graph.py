from fastapi import APIRouter, Depends, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from uuid import uuid4
from datetime import datetime
from typing import Annotated
import logging
import json
import asyncio

from src.models.schemas import StartRequest, GraphResponse, ResumeRequest
from src.models.status_enums import ExecutionStatus, ApprovalStatus
from src.services.explainable_agent import ExplainableAgent
from langchain_core.messages import HumanMessage
from src.services.explainable_agent import ExplainableAgentState

router = APIRouter(
    prefix="/graph/stream",
    tags=["streaming-graph"]
)

# Dependency functions that access app state
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

# Store run configurations for streaming
run_configs = {}

@router.post("/start", response_model=GraphResponse)
def create_graph_streaming(request: StartRequest):
    thread_id = request.thread_id or str(uuid4())
    
    run_configs[thread_id] = {
        "type": "start",
        "human_request": request.human_request
    }
    
    return GraphResponse(
        thread_id=thread_id,
        run_status="pending",
        assistant_response="",  # Empty string, will be built from streaming
        query=request.human_request,
        plan="",
        steps=[],
        final_result=None,
        total_time=None,
        overall_confidence=None
    )

@router.post("/resume", response_model=GraphResponse)
def resume_graph_streaming(request: ResumeRequest):
    thread_id = request.thread_id
    
    run_configs[thread_id] = {
        "type": "resume",
        "review_action": request.review_action,
        "human_comment": request.human_comment
    }
    
    return GraphResponse(
        thread_id=thread_id,
        run_status="pending",
        assistant_response=None
    )

@router.get("/{thread_id}")
async def stream_graph(request: Request, thread_id: str, agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]):
    # Check if thread_id exists in our configurations
    if thread_id not in run_configs:
        return {"error": "Thread ID not found. You must first call /graph/stream/create or /graph/stream/resume"}
    
    # Get the stored configuration
    run_data = run_configs[thread_id]
    config = {"configurable": {"thread_id": thread_id}}
    
    input_state = None
    if run_data["type"] == "start":
        event_type = "start"
        # Create the initial state for start operations
        initial_state = ExplainableAgentState(
            messages=[HumanMessage(content=run_data["human_request"])],
            query=run_data["human_request"],
            plan="",
            steps=[],
            step_counter=0,
            status="approved"
        )
        input_state = initial_state
    else:
        event_type = "resume"
        
        state_update = {"status": run_data["review_action"]}
        if run_data["human_comment"] is not None:
            state_update["human_comment"] = run_data["human_comment"]
        
        agent.graph.update_state(config, state_update)
        # For resume operations, we pass None as the input state
        input_state = None
    
    async def event_generator():       
        # Initial event with thread_id
        initial_data = json.dumps({"thread_id": thread_id})
        print(f"DEBUG: Sending initial {event_type} event with data: {initial_data}")

        yield {"event": event_type, "data": initial_data}
        
        try:
            print(f"DEBUG: Starting to stream graph messages for thread_id={thread_id}")
            for msg, metadata in agent.graph.stream(input_state, config, stream_mode="messages"):
                if await request.is_disconnected():
                    print("DEBUG: Client disconnected, breaking stream loop")
                    break
                    
                # Stream tokens from AI messages for real-time display
                if hasattr(msg, 'content') and msg.content:
                    if type(msg).__name__ in [ 'AIMessageChunk']:
                        # Check if it's not a tool call (actual assistant response)
                        if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                            node_name = metadata.get('langgraph_node', 'unknown')
                            
                            # Send small tokens for real-time streaming display
                            if type(msg).__name__ == 'AIMessageChunk':
                                token_data = json.dumps({
                                    "content": msg.content,
                                    "node": node_name,
                                    "type": "chunk"
                                })
                                yield {"event": "token", "data": token_data}
                            
                            # Send complete messages for saving/final processing
                            elif len(msg.content) > 50:  # Only send substantial complete messages
                                final_data = json.dumps({
                                    "content": msg.content,
                                    "node": node_name,
                                    "type": "complete"
                                })
                                yield {"event": "message", "data": final_data}
            
            # After streaming completes, check if human feedback is needed
            state = agent.graph.get_state(config)
            if state.next and 'human_feedback' in state.next:
                status_data = json.dumps({"status": "user_feedback"})
                print(f"DEBUG: Sending status event (feedback): {status_data}")
                yield {"event": "status", "data": status_data}
            else:
                status_data = json.dumps({"status": "finished"})
                print(f"DEBUG: Sending status event (finished): {status_data}")
                yield {"event": "status", "data": status_data}
                
            # Clean up the thread configuration after streaming is complete
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs")
                del run_configs[thread_id]
                
        except Exception as e:
            print(f"DEBUG: Exception in event_generator: {str(e)}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            
            # Clean up on error as well
            if thread_id in run_configs:
                print(f"DEBUG: Cleaning up thread_id={thread_id} from run_configs after error")
                del run_configs[thread_id]
    
    return EventSourceResponse(event_generator())

@router.get("/result/{thread_id}", response_model=GraphResponse)
def get_streaming_result(thread_id: str, agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]):
    """
    Get the final complete GraphResponse after streaming completes.
    This provides all the structured data the UI needs (steps, final_result, etc.)
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Get the final state from the agent
        state = agent.graph.get_state(config)
        if not state:
            raise HTTPException(status_code=404, detail=f"No graph execution found for thread_id: {thread_id}")
        
        next_nodes = state.next
        values = state.values
        query = values.get("query", "")
        checkpoint_id = None
        
        if hasattr(state, 'config') and state.config and 'configurable' in state.config:
            configurable = state.config['configurable']
            if 'checkpoint_id' in configurable:
                checkpoint_id = str(configurable['checkpoint_id'])
        
        if next_nodes and "human_feedback" in next_nodes:
            # Still waiting for user feedback
            execution_status = "user_feedback"
            assistant_response = values.get("assistant_response") or values.get("plan", "Plan generated - awaiting approval")
            plan = values.get("plan", "")
            
            return GraphResponse(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                query=query,
                run_status=execution_status,
                assistant_response=assistant_response,
                plan=plan,
                steps=values.get("steps", []),
                final_result=None,
                total_time=None,
                overall_confidence=None
            )
        else:
            # Execution completed - build complete response
            execution_status = "finished"
            messages = values.get("messages", [])
            
            # Get the last AI message as the assistant response
            assistant_response = ""
            for msg in reversed(messages):
                if (hasattr(msg, 'content') and msg.content and 
                    type(msg).__name__ == 'AIMessage' and
                    (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                    assistant_response = msg.content
                    break
            
            steps = values.get("steps", [])
            plan = values.get("plan", "")
            
            # Calculate metrics if we have steps
            total_time = None
            overall_confidence = None
            final_result = None
            
            if steps:
                # Calculate overall confidence
                confidences = [step.get("confidence", 0.8) for step in steps if "confidence" in step]
                overall_confidence = sum(confidences) / len(confidences) if confidences else 0.8
                
                from src.models.schemas import FinalResult
                final_result = FinalResult(
                    summary=assistant_response[:200] + "..." if len(assistant_response) > 200 else assistant_response,
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
        return GraphResponse(
            thread_id=thread_id,
            checkpoint_id=None,
            query="",
            run_status="error",
            assistant_response="",
            error=error_message
        )