from fastapi import APIRouter, Depends, Request, HTTPException
from uuid import uuid4
from datetime import datetime
from typing import Annotated

from src.models.schemas import StartRequest, GraphResponse, ResumeRequest
from src.services.explainable_agent import ExplainableAgent

router = APIRouter(
    prefix="/graph",
    tags=["graph"]
)

# Dependency functions that access app state
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent


def run_graph_and_response(explainable_agent: ExplainableAgent, input_state, config):
    
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
        
        if next_nodes and "human_feedback" in next_nodes:
            run_status = "user_feedback"
            # Get the plan from current state for user review
            current_values = state.values
            
            # Check if there's an assistant_response (for direct answers) or use plan
            assistant_response = current_values.get("assistant_response") or current_values.get("plan", "Plan generated - awaiting approval")
            plan = current_values.get("plan", "")
            
            return GraphResponse(
                thread_id=thread_id,
                run_status=run_status,
                assistant_response=assistant_response,
                plan=plan
            )
        else:
            run_status = "finished"
            
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
            
            # If no assistant response found from messages, try to get from final event
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
                    summary=assistant_response[:200] + "..." if len(assistant_response) > 200 else assistant_response,
                    details=f"Executed {len(steps)} steps successfully",
                    source="Database query execution",
                    inference="Based on database analysis and tool execution",
                    extra_explanation=f"Plan: {plan}"
                )
            
            return GraphResponse(
                thread_id=thread_id,
                run_status=run_status,
                assistant_response=assistant_response,
                plan=plan,
                steps=steps,
                final_result=final_result,
                total_time=total_time,
                overall_confidence=overall_confidence
            )
            
    except Exception as e:
        return GraphResponse(
            thread_id=config["configurable"]["thread_id"],
            run_status="error",
            error=str(e)
        )


@router.post("/start", response_model=GraphResponse)
def start_graph(
    request: StartRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
  
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create initial state for the explainable agent
    from langchain_core.messages import HumanMessage
    from src.services.explainable_agent import ExplainableAgentState
    
    initial_state = ExplainableAgentState(
        messages=[HumanMessage(content=request.human_request)],
        query=request.human_request,
        plan="",
        steps=[],
        step_counter=0,
        status="approved"  
    )
    
    return run_graph_and_response(agent, initial_state, config)


@router.post("/resume", response_model=GraphResponse)
def resume_graph(
    request: ResumeRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        # Get current state
        current_state = agent.graph.get_state(config)
        if not current_state:
            raise HTTPException(status_code=404, detail=f"No graph execution found for thread_id: {request.thread_id}")
        
        # Prepare state update
        state_update = {"status": request.review_action}
        if request.human_comment is not None:
            state_update["human_comment"] = request.human_comment
        
        print(f"State to update: {state_update}")
        
        agent.graph.update_state(config, state_update)
        
        # Continue execution
        return run_graph_and_response(agent, None, config)
        
    except Exception as e:
        if "thread_id" in str(e).lower() or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Graph execution not found for thread_id: {request.thread_id}")
        raise HTTPException(status_code=500, detail=f"Error resuming graph: {str(e)}")


@router.get("/status/{thread_id}")
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
            status = "user_feedback"
        elif next_nodes:
            status = "running"
        else:
            status = "finished"
        
        return {
            "thread_id": thread_id,
            "status": status,
            "next_nodes": list(next_nodes) if next_nodes else [],
            "plan": values.get("plan", ""),
            "step_count": len(values.get("steps", [])),
            "current_status": values.get("status", "unknown")
        }
        
    except Exception as e:
        if "thread_id" in str(e).lower() or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Graph execution not found for thread_id: {thread_id}")
        raise HTTPException(status_code=500, detail=f"Error getting graph status: {str(e)}")
