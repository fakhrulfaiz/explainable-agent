from typing import Optional, List, Dict, Any
from src.services.explainable_agent import ExplainableAgent
import logging

logger = logging.getLogger(__name__)

class AgentVisualizationService:
    """Service to fetch visualization data from agent checkpoints"""
    
    def __init__(self, explainable_agent: ExplainableAgent):
        self.agent = explainable_agent
    
    def get_visualization_data(self, thread_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get visualization data from a specific checkpoint
        
        Args:
            thread_id: The thread ID
            checkpoint_id: The specific checkpoint ID to fetch data from
            
        Returns:
            Dictionary with visualization data or None if not found
        """
        try:
            logger.info(f"Getting visualization data for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
            
            # Create config to get the state at specific checkpoint
            config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
            
            # Get the state from the agent
            state = self.agent.graph.get_state(config)
            
            if not state or not hasattr(state, 'values') or not state.values:
                logger.warning(f"No state found for thread_id: {thread_id}")
                return None
            
            values = state.values
            
            # Extract visualizations from the state
            visualizations = values.get("visualizations", [])
            
            if not visualizations:
                logger.info(f"No visualizations found in checkpoint {checkpoint_id}")
                return None
            
            # Normalize visualizations (similar to graph.py)
            normalized_visualizations = self._normalize_visualizations(visualizations)
            
            if not normalized_visualizations:
                logger.info(f"No valid visualizations found in checkpoint {checkpoint_id}")
                return None
            
            # Build visualization data response
            visualization_data = {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "visualizations": normalized_visualizations,
                "count": len(normalized_visualizations),
                "types": [viz.get("type", "unknown") for viz in normalized_visualizations]
            }
            
            logger.info(f"Successfully retrieved {len(normalized_visualizations)} visualizations from checkpoint {checkpoint_id}")
            return visualization_data
            
        except Exception as e:
            logger.error(f"Error getting visualization data for checkpoint {checkpoint_id}: {str(e)}")
            return None
    
    def _normalize_visualizations(self, visualizations: Any) -> List[Dict[str, Any]]:
        """
        Normalize visualization data to ensure consistent format
        Similar to the _normalize_visualizations function in graph.py
        """
        try:
            import json
            if not visualizations:
                return []
            normalized: List[Dict[str, Any]] = []
            for v in visualizations:
                if isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, dict):
                            normalized.append(parsed)
                    except Exception:
                        continue
                elif isinstance(v, dict):
                    normalized.append(v)
            return normalized
        except Exception:
            return []
    
    def get_visualization_summary(self, thread_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of visualization data from a specific checkpoint
        
        Args:
            thread_id: The thread ID
            checkpoint_id: The specific checkpoint ID
            
        Returns:
            Dictionary with visualization summary information
        """
        try:
            visualization_data = self.get_visualization_data(thread_id, checkpoint_id)
            
            if visualization_data is None:
                return None
            
            visualizations = visualization_data.get("visualizations", [])
            
            if not visualizations:
                return {
                    "visualization_count": 0,
                    "has_visualizations": False,
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id
                }
            
            # Calculate summary statistics
            viz_types = [viz.get("type", "unknown") for viz in visualizations]
            unique_types = list(set(viz_types))
            
            return {
                "visualization_count": len(visualizations),
                "has_visualizations": True,
                "checkpoint_id": checkpoint_id,
                "thread_id": thread_id,
                "visualization_types": unique_types,
                "visualizations_preview": [
                    {
                        "type": viz.get("type", "unknown"),
                        "title": viz.get("title", "Untitled"),
                        "data_points": len(viz.get("data", [])) if isinstance(viz.get("data"), list) else 0
                    }
                    for viz in visualizations[:3]  # First 3 visualizations as preview
                ]
            }
            
        except Exception as e:
            logger.error(f"Error fetching visualization summary for checkpoint {checkpoint_id}: {str(e)}")
            return None
