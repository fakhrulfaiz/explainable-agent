from fastapi import APIRouter, Depends, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from uuid import uuid4
from datetime import datetime
from typing import Annotated
import logging
import json
import asyncio
import time

from src.models.schemas import StartRequest, GraphResponse, ResumeRequest
from src.models.status_enums import ExecutionStatus, ApprovalStatus
from src.services.explainable_agent2 import ExplainableAgent
from langchain_core.messages import HumanMessage
from src.services.explainable_agent2 import ExplainableAgentState
from src.repositories.dependencies import get_message_management_service
from src.services.message_management_service import MessageManagementService
from src.utils.approval_utils import clear_previous_approvals

logger = logging.getLogger(__name__)

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
        "human_request": request.human_request,
        "use_planning": request.use_planning,
        "use_explainer": request.use_explainer,
        "agent_type": request.agent_type
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
async def stream_graph(request: Request, thread_id: str, 
                      agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)],
                      message_service: Annotated[MessageManagementService, Depends(get_message_management_service)]):
    # Check if thread_id exists in our configurations
    if thread_id not in run_configs:
        return {"error": "Thread ID not found. You must first call /graph/stream/create or /graph/stream/resume"}
    
    # Get the stored configuration
    run_data = run_configs[thread_id]
    config = {"configurable": {"thread_id": thread_id}}
    
    input_state = None
    if run_data["type"] == "start":
        event_type = "start"
        use_planning_value = run_data.get("use_planning", True)
        
        
        initial_state = ExplainableAgentState(
            messages=[HumanMessage(content=run_data["human_request"])],
            query=run_data["human_request"],
            plan="",
            steps=[],
            step_counter=0,
            status="approved",
            use_planning=use_planning_value,
            use_explainer=run_data.get("use_explainer", True),
            agent_type=run_data.get("agent_type", "assistant"),
            visualizations=[]
        )
        input_state = initial_state
    else:
        event_type = "resume"
        
        # Save user feedback message to database
        print(f"Feedback debug - message_service: {message_service is not None}, human_comment: '{run_data.get('human_comment')}'")
        if message_service and run_data.get("human_comment"):
            try:
                saved_feedback = await message_service.save_user_message(
                    thread_id=thread_id,
                    content=run_data["human_comment"]
                )
                print(f"Saved user feedback message {saved_feedback.message_id} for thread {thread_id}")
            except Exception as e:
                print(f"Failed to save user feedback message for thread {thread_id}: {e}")
        else:
            print(f"Skipping feedback save - message_service: {message_service is not None}, human_comment: '{run_data.get('human_comment')}'")
        
        state_update = {"status": run_data["review_action"]}
        if run_data["human_comment"] is not None:
            state_update["human_comment"] = run_data["human_comment"]
        
        agent.graph.update_state(config, state_update)
        input_state = None
    
    async def event_generator():       
        buffer = ""
        # Track previous state to detect step changes
        previous_steps = []
        
        # Initial event with thread_id
        initial_data = json.dumps({"thread_id": thread_id})

        yield {"event": event_type, "data": initial_data}
        
        try:
            for msg, metadata in agent.graph.stream(input_state, config, stream_mode="messages"):
                if await request.is_disconnected():
                    break
                
           
                current_state = agent.graph.get_state(config)
                if current_state and current_state.values:
                    current_steps = current_state.values.get("steps", [])
    
                    # Emit step info when new steps are added
                    if len(current_steps) > len(previous_steps):
                        new_steps = current_steps[len(previous_steps):]
                        for step in new_steps:
                            # Only emit steps that have both tool_name and decision
                            if not step.get("tool_name") or not step.get("decision"):
                                continue
                            
                            step_data = json.dumps({
                                "step": {
                                    "id": step.get("id", 0),
                                    "tool_name": step.get("tool_name", ""),
                                    "decision": step.get("decision", "")
                                }
                            })
                            yield {"event": "step_added", "data": step_data}
                            previous_steps = current_steps.copy()
                    
                    
                # Handle different message types
                node_name = metadata.get('langgraph_node', 'unknown')
                
                # Handle tool calls (these might not have content)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # Filter: only emit tool calls from planner or agent nodes
                    if node_name in ['agent']:
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.get('name', '')
                            tool_id = tool_call.get('id', '')
            
                            if not tool_name or not tool_id:
                                continue
                            
                            # Exclude specific tools from streaming
                            if tool_name == 'transfer_to_data_exploration':
                                continue
                                
                            tool_call_data = json.dumps({
                                "status": "tool_call",
                                "tool_name": tool_name,
                                "node": node_name,
                                "tool_id": tool_id
                            })
                            yield {"event": "tool_call", "data": tool_call_data}
                
                # Handle tool results (from ToolMessage)
                elif hasattr(msg, 'tool_call_id') and hasattr(msg, 'content'):
                    # This is a tool result message 
        
                    tool_result_data = json.dumps({
                        "status": "tool_result",
                        "tool_call_id": msg.tool_call_id,
                        "node": node_name,
                        "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content  # Truncate long results
                    })
                    yield {"event": "tool_result", "data": tool_result_data}
                
                # Stream tokens from AI messages for real-time display
                elif hasattr(msg, 'content') and msg.content:
                    if type(msg).__name__ in ['AIMessageChunk']:
                        # Filter: only emit tokens/messages from planner or agent nodes
                        if node_name not in ['planner', 'agent']:
                            continue
                    
                        # Preserve whitespace inside chunks to avoid concatenated words
                        chunk_text = msg.content
                        if chunk_text.startswith("{") or buffer:
                            buffer += chunk_text
                            try:
                                parsed = json.loads(buffer)
                               
                                yield {
                                "event": "message",
                                "data": json.dumps({
                                    "content": parsed.get("content", ""),
                                    "node": node_name,
                                    "type": "feedback_answer"
                                    })
                                    }
                                buffer = ""  # reset after full parse
                                
                            except json.JSONDecodeError:
                                continue
                        else:
                            # Normal token streaming
                            token_data = json.dumps({
                            "content": msg.content,
                            "node": node_name,
                            "type": "chunk"
                             })
                            yield {"event": "token", "data": token_data}
                    elif type(msg).__name__ in ['AIMessage']:
                        yield {"event": "message", "data": json.dumps({
                            "content": msg.content,
                            "node": node_name,
                            "type": "message"
                        })}
            
            # After streaming completes, emit final payloads
            state = agent.graph.get_state(config)
            values = getattr(state, 'values', {}) or {}
            messages = values.get("messages", [])
            steps = values.get("steps", [])
            plan = values.get("plan", "")
            query = values.get("query", "")
            # Determine assistant final response
            assistant_response = ""
            for m in reversed(messages):
                if (hasattr(m, 'content') and m.content and type(m).__name__ == 'AIMessage' and (not hasattr(m, 'tool_calls') or not m.tool_calls)):
                    assistant_response = m.content
                    break

            # Compute checkpoint_id if present
            checkpoint_id = None
            try:
                if hasattr(state, 'config') and state.config and 'configurable' in state.config:
                    configurable = state.config['configurable']
                    if 'checkpoint_id' in configurable:
                        checkpoint_id = str(configurable['checkpoint_id'])
            except Exception:
                checkpoint_id = None

            # Overall confidence
            overall_confidence = None
            if steps:
                confidences = [s.get("confidence", 0.8) for s in steps if isinstance(s, dict) and "confidence" in s]
                overall_confidence = (sum(confidences) / len(confidences)) if confidences else 0.8

            # Build final_result summary
            try:
                from src.models.schemas import FinalResult
                final_result_summary = FinalResult(
                    summary=assistant_response,
                    details=f"Executed {len(steps)} steps successfully",
                    source="Database query execution",
                    inference="Based on database analysis and tool execution",
                    extra_explanation=f"Plan: {plan}"
                )
                final_result_dict = final_result_summary.model_dump()
            except Exception:
                final_result_dict = {
                    "summary": (assistant_response[:200] + "...") if isinstance(assistant_response, str) and len(assistant_response) > 200 else assistant_response,
                    "details": f"Executed {len(steps)} steps successfully",
                    "source": "Database query execution",
                    "inference": "Based on database analysis and tool execution",
                    "extra_explanation": f"Plan: {plan}"
                }

            # Send status event (user_feedback or finished)
            if state.next and 'human_feedback' in state.next:
                # Save assistant message that needs approval when waiting for user feedback
                if assistant_response and message_service:
                    try:
                        # Check if this is a replan and clear previous approval flags
                        response_type = values.get("response_type")
                        if response_type == "replan":
                            logger.info(f"Replan detected in streaming - clearing needs_approval from previous messages in thread {thread_id}")
                            await clear_previous_approvals(thread_id, message_service)
                        
                        saved_message = await message_service.save_assistant_message(
                            thread_id=thread_id,
                            content=assistant_response,
                            message_type="message",
                            checkpoint_id=checkpoint_id,
                            needs_approval=True  # This message needs approval
                        )
                        logger.info(f"Saved assistant message {saved_message.message_id} for approval in thread {thread_id}")
                    except Exception as e:
                        logger.error(f"Failed to save assistant message for approval in thread {thread_id}: {e}")
                
                status_data = json.dumps({"status": "user_feedback"})
                yield {"event": "status", "data": status_data}
            else:
                status_data = json.dumps({"status": "finished"})
                yield {"event": "status", "data": status_data}

                # Save messages to database when execution finishes
                try:
                    # Save main assistant message
                    if assistant_response:
                        await message_service.save_assistant_message(
                            thread_id=thread_id,
                            content=assistant_response,
                            message_type="message",
                            checkpoint_id=checkpoint_id,
                            needs_approval=False
                        )
                    
                    # Save explorer message if steps exist
                    if steps and len(steps) > 0:
                        explorer_content = f"Data exploration completed with {len(steps)} steps"
                        if final_result_dict:
                            explorer_content += f": {final_result_dict.get('summary', '')}"
                        
                        await message_service.save_assistant_message(
                            thread_id=thread_id,
                            content=explorer_content,
                            message_type="explorer",
                            checkpoint_id=checkpoint_id,
                            needs_approval=False
                        )
                    
                    # Save visualization message if visualizations exist
                    visualizations = values.get("visualizations", [])
                    if visualizations and len(visualizations) > 0:
                        viz_types = list({v.get("type", "unknown") for v in visualizations if isinstance(v, dict)})
                        viz_content = f"Generated {len(visualizations)} visualization(s): {', '.join(viz_types)}"
                        
                        await message_service.save_assistant_message(
                            thread_id=thread_id,
                            content=viz_content,
                            message_type="visualization",
                            checkpoint_id=checkpoint_id,
                            needs_approval=False
                        )
                        
                except Exception as e:
                    print(f"Failed to save messages for thread {thread_id}: {e}")

                # Emit enriched completed payload
                completed_payload = {
                    "success": True,
                    "data": {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "run_status": "finished",
                        "assistant_response": assistant_response,
                        "query": query,
                        "plan": plan,
                        "error": None,
                        "steps": steps,
                        "final_result": final_result_dict,
                        "total_time": None,
                        "overall_confidence": overall_confidence
                    },
                    "message": f"Explorer data retrieved successfully for checkpoint {checkpoint_id}" if checkpoint_id else "Explorer data retrieved successfully"
                }
                yield {"event": "completed", "data": json.dumps(completed_payload)}

                # Visualizations follow-up
                try:
                    from .graph import _normalize_visualizations  # reuse normalization helper
                except Exception:
                    _normalize_visualizations = lambda v: v if isinstance(v, list) else []
                visualizations = _normalize_visualizations(values.get("visualizations", []))
                try:
                    visualization_types = list({v.get("type") for v in visualizations if isinstance(v, dict) and v.get("type")})
                    visualizations_payload = {
                        "success": True,
                        "data": {
                            "thread_id": thread_id,
                            "checkpoint_id": checkpoint_id,
                            "visualizations": visualizations,
                            "count": len(visualizations),
                            "types": visualization_types
                        },
                        "message": f"Visualization data retrieved successfully for checkpoint {checkpoint_id}" if checkpoint_id else "Visualization data retrieved successfully"
                    }
                    yield {"event": "visualizations_ready", "data": json.dumps(visualizations_payload)}
                except Exception:
                    pass
                
            # Clean up the thread configuration after streaming is complete
            if thread_id in run_configs:
                del run_configs[thread_id]
                
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            
            # Clean up on error as well
            if thread_id in run_configs:
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