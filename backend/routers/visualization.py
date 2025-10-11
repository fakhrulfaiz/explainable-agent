from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import Annotated
from src.services.explainable_agent import ExplainableAgent
from src.services.agent_visualization_service import AgentVisualizationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/graph/visualization",
    tags=["visualization"]
)

# Dependency functions
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

def get_visualization_service(agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]) -> AgentVisualizationService:
    return AgentVisualizationService(agent)

@router.get("/data")
def get_visualization_data(
    thread_id: str = Query(..., description="Thread ID"),
    checkpoint_id: str = Query(..., description="Checkpoint ID"),
    visualization_service: Annotated[AgentVisualizationService, Depends(get_visualization_service)] = None
):
    """
    Get visualization data from a specific checkpoint for restoring visualization state
    """
    try:
        logger.info(f"Fetching visualization data for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
        
        visualization_data = visualization_service.get_visualization_data(thread_id, checkpoint_id)
        
        if visualization_data is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No visualization data found for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}"
            )
        
        return {
            "success": True,
            "data": visualization_data,
            "message": f"Visualization data retrieved successfully for checkpoint {checkpoint_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching visualization data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching visualization data: {str(e)}")

@router.get("/summary")
def get_visualization_summary(
    thread_id: str = Query(..., description="Thread ID"),
    checkpoint_id: str = Query(..., description="Checkpoint ID"),
    visualization_service: Annotated[AgentVisualizationService, Depends(get_visualization_service)] = None
):
    """
    Get a summary of visualization data from a specific checkpoint
    """
    try:
        logger.info(f"Fetching visualization summary for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
        
        summary = visualization_service.get_visualization_summary(thread_id, checkpoint_id)
        
        if summary is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No visualization data found for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}"
            )
        
        return {
            "success": True,
            "data": summary,
            "message": f"Visualization summary retrieved successfully for checkpoint {checkpoint_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching visualization summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching visualization summary: {str(e)}")
