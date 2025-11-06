from fastapi import APIRouter, Depends, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from uuid import uuid4
from datetime import datetime
from typing import Annotated, Any
import logging
import json
import asyncio
import time
import time as _time

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

def _extract_stream_or_message_id(msg: Any, preferred_key: str = 'message_id') -> Any:
    """Robustly extracts a stream ID (string) or message ID (int) from a chunk,
    falling back to a dynamic timestamp if needed."""
    # Prefer explicit tool_call_id when present (useful for associating streams with tool calls)
    tool_call_id = getattr(msg, 'tool_call_id', None)
    if tool_call_id is not None and tool_call_id != "":
        if isinstance(tool_call_id, str) and tool_call_id.isdigit():
            return int(tool_call_id)
        return tool_call_id
    msg_id = getattr(msg, 'id', None)
    if not msg_id and hasattr(msg, 'response_metadata'):
        meta = getattr(msg, 'response_metadata') or {}
        for key in [preferred_key, 'id']:
            mid = meta.get(key)
            if mid is not None:
                msg_id = mid
                break
    if isinstance(msg_id, str):
        try:
            if msg_id.isdigit():
                return int(msg_id)
        except:
            pass
    if msg_id is None or (isinstance(msg_id, str) and not msg_id):
        return int(_time.time() * 1000000)
    return msg_id

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
        assistant_response="", 
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
        
        # Track tool calls to match with their results
        pending_tool_calls = {}  # {tool_call_id: {tool_name, args, node}}
        
        # Initial event with thread_id
        initial_data = json.dumps({"thread_id": thread_id})
        yield {"event": event_type, "data": initial_data}
        
        try:
            for msg, metadata in agent.graph.stream(input_state, config, stream_mode="messages"):
                if await request.is_disconnected():
                    break
                
                # Handle different message types
                node_name = metadata.get('langgraph_node', 'unknown')
                
                # Handle tool call chunks - accumulate args but don't emit until we have tool_id
                if hasattr(msg, 'tool_call_chunks') and msg.tool_call_chunks:
                    if node_name in ['agent']:
                        for chunk in msg.tool_call_chunks:
                            chunk_dict = chunk if isinstance(chunk, dict) else chunk.dict() if hasattr(chunk, 'dict') else {}
                            chunk_id = chunk_dict.get('id')
                            chunk_index = chunk_dict.get('index')
                            chunk_name = chunk_dict.get('name')
                            chunk_args_str = chunk_dict.get('args', '')
                            
                            # Filter out transfer_to_data_exploration EARLY before accumulation
                            # Check both current chunk name and any existing tool_name for this chunk_id
                            if chunk_name == 'transfer_to_data_exploration':
                                # Clean up any partial accumulation for this tool
                                if chunk_id and chunk_id in pending_tool_calls:
                                    del pending_tool_calls[chunk_id]
                                # Also check index-based keys
                                if chunk_index is not None:
                                    index_key = f"index_{chunk_index}"
                                    if index_key in pending_tool_calls and pending_tool_calls[index_key].get('tool_name') == 'transfer_to_data_exploration':
                                        del pending_tool_calls[index_key]
                                continue
                            
                            # Also skip if we already know this chunk_id is transfer_to_data_exploration
                            if chunk_id and chunk_id in pending_tool_calls:
                                existing_tool_name = pending_tool_calls[chunk_id].get('tool_name', '')
                                if existing_tool_name == 'transfer_to_data_exploration':
                                    # Clean up the entry
                                    del pending_tool_calls[chunk_id]
                                    continue
                            
                            if not chunk_args_str:
                                continue
                            
                            # Use index to track chunks before we get id
                            # Index 0 = first tool_call, index 1 = second, etc.
                            tool_key = chunk_id if chunk_id else (f"index_{chunk_index}" if chunk_index is not None else None)
                            
                            if not tool_key:
                                continue
                            
                            # Initialize if first chunk
                            if tool_key not in pending_tool_calls:
                                pending_tool_calls[tool_key] = {
                                    'tool_name': '',
                                    'args_string': '',
                                    'node': node_name,
                                    'chunk_id': chunk_id,
                                    'index': chunk_index,
                                    'ready_to_emit': False  # Don't emit until we have real id/name
                                }
                            
                            # Update when id/name arrives
                            if chunk_id:
                                # Migrate from index key to id key if needed
                                if tool_key != chunk_id and tool_key.startswith('index_'):
                                    pending_tool_calls[chunk_id] = pending_tool_calls.pop(tool_key)
                                    tool_key = chunk_id
                                pending_tool_calls[tool_key]['chunk_id'] = chunk_id
                            
                            if chunk_name:
                                # Double-check we're not accidentally tracking transfer_to_data_exploration
                                if chunk_name == 'transfer_to_data_exploration':
                                    if tool_key in pending_tool_calls:
                                        del pending_tool_calls[tool_key]
                                    continue
                                pending_tool_calls[tool_key]['tool_name'] = chunk_name
                            
                            # Accumulate args
                            pending_tool_calls[tool_key]['args_string'] += chunk_args_str
                            
                            # Only emit if we have BOTH tool_id AND tool_name (not just id)
                            # Otherwise wait for tool_calls message which has both
                            actual_tool_id = pending_tool_calls[tool_key].get('chunk_id')
                            current_tool_name = pending_tool_calls[tool_key]['tool_name']
                            
                            if actual_tool_id and current_tool_name and not tool_key.startswith('index_'):
                                # Double-check we're not emitting transfer_to_data_exploration
                                if current_tool_name == 'transfer_to_data_exploration':
                                    continue
                                
                                # Mark as ready and emit chunk
                                if not pending_tool_calls[tool_key].get('ready_to_emit'):
                                    pending_tool_calls[tool_key]['ready_to_emit'] = True
                                
                                # Emit tool_call event with args
                                tool_call_data = json.dumps({
                                    "status": "tool_call",
                                    "tool_id": actual_tool_id,
                                    "tool_name": current_tool_name,
                                    "args": chunk_args_str,
                                    "node": node_name
                                })
                                yield {"event": "tool_call", "data": tool_call_data}
                
                # Handle complete tool_calls messages (get real id/name and start emitting accumulated chunks)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    if node_name in ['agent']:
                        # FIRST PASS: Identify and clean up ALL transfer_to_data_exploration entries
                        transfer_tool_ids = set()
                        transfer_indices = set()
                        
                        for idx, tool_call in enumerate(msg.tool_calls):
                            tool_call_dict = tool_call if isinstance(tool_call, dict) else tool_call.dict() if hasattr(tool_call, 'dict') else {}
                            tool_name = tool_call_dict.get('name', '')
                            tool_id = tool_call_dict.get('id', '')
                            
                            if tool_name == 'transfer_to_data_exploration' and tool_id:
                                transfer_tool_ids.add(tool_id)
                                transfer_indices.add(idx)
                        
                        # Clean up ALL entries matching transfer_to_data_exploration
                        # Be conservative: only clean up if we're certain it's transfer_to_data_exploration
                        for key in list(pending_tool_calls.keys()):
                            info = pending_tool_calls[key]
                            chunk_id = info.get('chunk_id')
                            stored_index = info.get('index')
                            tool_name = info.get('tool_name', '')
                            
                            # Clean up if:
                            # 1. chunk_id matches a transfer tool_id (most reliable)
                            # 2. tool_name is explicitly transfer_to_data_exploration
                            # Note: We don't clean up by index alone to avoid false positives
                            # Entries with matching index but no chunk_id/tool_name will be handled
                            # by matching logic which verifies tool_name before using accumulated args
                            should_clean = False
                            
                            if chunk_id and chunk_id in transfer_tool_ids:
                                should_clean = True
                            elif tool_name == 'transfer_to_data_exploration':
                                should_clean = True
                            
                            if should_clean:
                                del pending_tool_calls[key]
                        
                        # SECOND PASS: Process remaining tool calls
                        # Track which tool_ids we've seen and matched
                        seen_tool_ids = set()
                        matched_indices = set()
                        
                        for idx, tool_call in enumerate(msg.tool_calls):
                            tool_call_dict = tool_call if isinstance(tool_call, dict) else tool_call.dict() if hasattr(tool_call, 'dict') else {}
                            tool_name = tool_call_dict.get('name', '')
                            tool_id = tool_call_dict.get('id', '')
                            
                            if not tool_id:
                                continue
                            
                            # Skip transfer_to_data_exploration (already cleaned up)
                            if tool_name == 'transfer_to_data_exploration':
                                continue
                            
                            seen_tool_ids.add(tool_id)
                            
                            # Find entry that was accumulating by chunk_id or index
                            tool_info = None
                            matching_key = None
                            
                            # First try to match by chunk_id (most reliable)
                            for key, info in list(pending_tool_calls.items()):
                                if info.get('chunk_id') == tool_id:
                                    # Verify it's not transfer_to_data_exploration (should be cleaned already)
                                    if info.get('tool_name') != 'transfer_to_data_exploration':
                                        tool_info = info
                                        matching_key = key
                                        break
                            
                            # If not found by chunk_id, try matching by index position (idx) in tool_calls array
                            # This works when chunks arrived with index matching the position in tool_calls
                            if not tool_info:
                                index_key = f"index_{idx}"
                                if index_key in pending_tool_calls:
                                    entry = pending_tool_calls[index_key]
                                    entry_chunk_id = entry.get('chunk_id')
                                    entry_tool_name = entry.get('tool_name', '')
                                    entry_args = entry.get('args_string', '')
                                    
                                    # Only use if:
                                    # 1. chunk_id matches this tool_id (most reliable), OR
                                    # 2. It doesn't have a chunk_id yet AND it has no args_string (fresh entry), OR
                                    # 3. It has a matching tool_name (even without chunk_id)
                                    # 4. It's not transfer_to_data_exploration
                                    # 5. It hasn't been matched to another tool
                                    can_use = False
                                    if entry_chunk_id == tool_id:
                                        can_use = True
                                    elif not entry_chunk_id and not entry_args:
                                        # Fresh entry with no data yet - safe to use
                                        can_use = True
                                    elif not entry_chunk_id and entry_tool_name == tool_name:
                                        # Matching tool_name even without chunk_id - likely correct
                                        can_use = True
                                    
                                    if can_use and \
                                       entry_tool_name != 'transfer_to_data_exploration' and \
                                       idx not in matched_indices:
                                        tool_info = entry
                                        matching_key = index_key
                                        matched_indices.add(idx)
                                        break
                            
                            # If still not found, try to find any unmatched index entry by stored_index
                            # This handles cases where chunks arrived in separate messages with their own indexing
                            if not tool_info:
                                for key, info in list(pending_tool_calls.items()):
                                    if key.startswith('index_'):
                                        stored_idx = info.get('index')
                                        existing_chunk_id = info.get('chunk_id')
                                        existing_tool_name = info.get('tool_name', '')
                                        existing_args = info.get('args_string', '')
                                        
                                        # Match by stored_index matching current position
                                        if stored_idx == idx and idx not in matched_indices:
                                            # Only use if we can verify it's correct:
                                            # 1. chunk_id matches, OR
                                            # 2. tool_name matches, OR
                                            # 3. No chunk_id and no args (fresh entry)
                                            can_use = False
                                            if existing_chunk_id == tool_id:
                                                can_use = True
                                            elif existing_tool_name == tool_name:
                                                can_use = True
                                            elif not existing_chunk_id and not existing_args:
                                                can_use = True
                                            
                                            if can_use and existing_tool_name != 'transfer_to_data_exploration':
                                                tool_info = info
                                                matching_key = key
                                                matched_indices.add(idx)
                                                break
                            
                            # Migrate to tool_id key if needed
                            if tool_info and matching_key and matching_key != tool_id:
                                pending_tool_calls[tool_id] = pending_tool_calls.pop(matching_key)
                            
                            if not tool_info:
                                pending_tool_calls[tool_id] = {
                                    'tool_name': tool_name,
                                    'args_string': '',
                                    'node': node_name,
                                    'chunk_id': tool_id,
                                    'ready_to_emit': True
                                }
                            else:
                                # Update with real name and id
                                tool_info['tool_name'] = tool_name
                                tool_info['chunk_id'] = tool_id
                                tool_info['ready_to_emit'] = True
                            
                            # Emit tool_call event with accumulated args (or empty {} if no args)
                            args_string = pending_tool_calls[tool_id].get('args_string', '')
                            
                            # Parse args_string to get clean JSON for emission
                            if args_string:
                                try:
                                    # Try to parse the accumulated args string
                                    parsed_args = json.loads(args_string)
                                    args_for_emission = json.dumps(parsed_args)
                                except json.JSONDecodeError:
                                    # If not valid JSON yet, try to extract last complete JSON object
                                    brace_count = 0
                                    json_start = None
                                    last_complete_json = None
                                    for i, char in enumerate(args_string):
                                        if char == '{':
                                            if brace_count == 0:
                                                json_start = i
                                            brace_count += 1
                                        elif char == '}':
                                            brace_count -= 1
                                            if brace_count == 0 and json_start is not None:
                                                try:
                                                    parsed = json.loads(args_string[json_start:i+1])
                                                    if isinstance(parsed, dict):
                                                        last_complete_json = parsed
                                                except:
                                                    pass
                                                json_start = None
                                    if last_complete_json:
                                        args_for_emission = json.dumps(last_complete_json)
                                    else:
                                        args_for_emission = args_string
                            else:
                                # No args accumulated - emit empty dict
                                args_for_emission = "{}"
                            
                            # Always emit tool_call event (even with empty args)
                            tool_call_data = json.dumps({
                                "status": "tool_call",
                                "tool_id": tool_id,
                                "tool_name": tool_name,
                                "args": args_for_emission,
                                "node": node_name
                            })
                            yield {"event": "tool_call", "data": tool_call_data}
                
                # Handle tool results (match with tool calls to provide complete info)
                elif hasattr(msg, 'tool_call_id') and hasattr(msg, 'content'):
                    tool_call_id = msg.tool_call_id
                    
                    # Find tool_info - could be keyed by tool_call_id or have it in chunk_id
                    tool_info = pending_tool_calls.get(tool_call_id)
                    if not tool_info:
                        # Search for entry with matching chunk_id
                        for key, info in pending_tool_calls.items():
                            if info.get('chunk_id') == tool_call_id:
                                tool_info = info
                                break
                    
                    if not tool_info:
                        tool_info = {}
                    
                    # Filter out transfer_to_data_exploration results
                    tool_name = tool_info.get('tool_name', 'unknown')
                    if tool_name == 'transfer_to_data_exploration':
                        # Clean up and skip
                        if tool_call_id in pending_tool_calls:
                            del pending_tool_calls[tool_call_id]
                        continue
                    
                    # Get full input args from accumulated string
                    input_args = {}
                    if tool_info.get('args_string'):
                        try:
                            input_args = json.loads(tool_info['args_string'])
                        except:
                            # Find last complete JSON object
                            args_string = tool_info['args_string']
                            last_complete_json = None
                            brace_count = 0
                            json_start = None
                            for i, char in enumerate(args_string):
                                if char == '{':
                                    if brace_count == 0:
                                        json_start = i
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0 and json_start is not None:
                                        try:
                                            parsed = json.loads(args_string[json_start:i+1])
                                            if isinstance(parsed, dict):
                                                last_complete_json = parsed
                                        except:
                                            pass
                                        json_start = None
                            if last_complete_json:
                                input_args = last_complete_json
                    
                    tool_result_data = json.dumps({
                        "status": "tool_result",
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "node": node_name,
                        "input": input_args,  # Full input parameters
                        "output": msg.content  # Full output (no truncation)
                    })
                    yield {"event": "tool_result", "data": tool_result_data}
                    
                    # Clean up after emitting
                    if tool_call_id in pending_tool_calls:
                        del pending_tool_calls[tool_call_id]
                
                # Stream tokens from AI messages for real-time display
                elif hasattr(msg, 'content') and msg.content:
                    if type(msg).__name__ in ['AIMessageChunk']:
                        # Filter: only emit tokens/messages from planner or agent nodes
                        if node_name not in ['planner', 'agent', 'tool_explanation']:
                            continue
                    
                        # Preserve whitespace inside chunks to avoid concatenated words
                        chunk_text = msg.content
                        # Extract a stable message id for streaming chunks
                        msg_id = _extract_stream_or_message_id(msg, preferred_key='message_id')
                        if chunk_text.startswith("{") or buffer:
                            buffer += chunk_text
                            try:
                                parsed = json.loads(buffer)
                               
                                yield {
                                "event": "message",
                                "data": json.dumps({
                                    "content": parsed.get("content", ""),
                                    "node": node_name,
                                    "type": "feedback_answer",
                                    "stream_id": msg_id
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
                                "type": "chunk",
                                "stream_id": msg_id
                            })
                            yield {"event": "token", "data": token_data}
                    elif type(msg).__name__ in ['AIMessage']:
                        msg_id_final = _extract_stream_or_message_id(msg, preferred_key='stream_id')
                        yield {"event": "message", "data": json.dumps({
                            "content": msg.content,
                            "node": node_name,
                            "type": "message",
                            "message_id": msg_id_final
                        })}
            
            # After streaming completes, emit final payloads
            state = agent.graph.get_state(config)
            values = getattr(state, 'values', {}) or {}
            messages = values.get("messages", [])
            steps = values.get("steps", [])
            plan = values.get("plan", "")
            query = values.get("query", "")
            # Determine assistant final response and its message_id
            assistant_response = ""
            assistant_message_id: int | None = None
            for m in reversed(messages):
                if (hasattr(m, 'content') and m.content and type(m).__name__ == 'AIMessage' and (not hasattr(m, 'tool_calls') or not m.tool_calls)):
                    assistant_response = m.content
                    # Extract a numeric message id if present
                    try:
                        extracted = _extract_stream_or_message_id(m, preferred_key='message_id')
                        assistant_message_id = int(extracted) if isinstance(extracted, (int, str)) and str(extracted).isdigit() else None
                    except Exception:
                        assistant_message_id = None
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
                            needs_approval=True,  # This message needs approval
                            message_id=assistant_message_id
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
                            needs_approval=False,
                            message_id=assistant_message_id
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