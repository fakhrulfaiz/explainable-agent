from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import Annotated
from src.services.explainable_agent import ExplainableAgent
from src.services.agent_explorer_service import AgentExplorerService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/explorer",
    tags=["explorer"]
)

# Dependency functions
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

def get_explorer_service(agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]) -> AgentExplorerService:
    return AgentExplorerService(agent)

@router.get("/data")
def get_explorer_data(
    thread_id: str = Query(..., description="Thread ID"),
    checkpoint_id: str = Query(..., description="Checkpoint ID"),
    explorer_service: Annotated[AgentExplorerService, Depends(get_explorer_service)] = None
):
    """
    Get explorer data from a specific checkpoint for restoring explorer state
    """
    try:
        logger.info(f"Fetching explorer data for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
        
        explorer_data = explorer_service.get_explorer_data(thread_id, checkpoint_id)
        
        if explorer_data is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No explorer data found for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}"
            )
        
        return {
            "success": True,
            "data": explorer_data,
            "message": f"Explorer data retrieved successfully for checkpoint {checkpoint_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching explorer data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching explorer data: {str(e)}")
