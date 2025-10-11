from typing import Optional, List, Dict, Any
from src.services.explainable_agent import ExplainableAgent
from src.models.schemas import StepExplanation, FinalResult
import logging

logger = logging.getLogger(__name__)

class AgentExplorerService:
    """Service to fetch step data and exploration details from agent checkpoints"""
    
    def __init__(self, explainable_agent: ExplainableAgent):
        self.agent = explainable_agent
    
    def get_explorer_data(self, thread_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Main method to get complete explorer data in ExplorerResult format
        This can be directly used with setExplorerData() in the frontend
        
        Args:
            thread_id: The thread ID
            checkpoint_id: The specific checkpoint ID to fetch data from
            
        Returns:
            Dictionary in ExplorerResult format or None if not found
        """
        try:
            logger.info(f"Getting explorer data for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
            
            # Create config to get the state at specific checkpoint
            config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
            
            # Get the state from the agent
            state = self.agent.graph.get_state(config)
            
            if not state or not hasattr(state, 'values') or not state.values:
                logger.warning(f"No state found for thread_id: {thread_id}")
                return None
            
            values = state.values
            
            # Extract steps data
            steps_data = values.get("steps", [])
            steps = []
            
            for step_data in steps_data:
                if isinstance(step_data, dict):
                    step = {
                        "id": step_data.get("id", 0),
                        "type": step_data.get("type", "unknown"),
                        "decision": step_data.get("decision", ""),
                        "reasoning": step_data.get("reasoning", ""),
                        "input": step_data.get("input", ""),
                        "output": step_data.get("output", ""),
                        "confidence": step_data.get("confidence", 0.0),
                        "why_chosen": step_data.get("why_chosen", ""),
                        "timestamp": step_data.get("timestamp", "")
                    }
                    steps.append(step)
            
            # Calculate overall confidence
            overall_confidence = None
            if steps:
                confidences = [step["confidence"] for step in steps if step["confidence"] > 0]
                overall_confidence = sum(confidences) / len(confidences) if confidences else 0.8
            
            last_message = None
            if values.get("messages", []):
                messages = values.get("messages", [])
                for msg in reversed(messages):
                    if (hasattr(msg, 'content') and msg.content and 
                        type(msg).__name__ == 'AIMessage' and
                        (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                        last_message = msg.content
                        break
            
            # Create final result if we have steps
            final_result = None
            if steps:
                final_result = {
                    "summary": last_message,
                    "details": f"Executed {len(steps)} steps successfully",
                    "source": "Database query execution",
                    "inference": "Based on database analysis and tool execution",
                    "extra_explanation": f"Plan: {values.get('plan', '')}"
                }
            
            # Build the ExplorerResult format
            explorer_result = {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "run_status": "finished",
                "assistant_response": last_message,
                "query": values.get("query", ""),  # Include the user's original question
                "plan": values.get("plan", ""),
                "error": None,
                "steps": steps if steps else None,
                "final_result": final_result,
                "total_time": None,  # Not available from checkpoint
                "overall_confidence": overall_confidence
            }
            
            logger.info(f"Successfully built explorer data with {len(steps)} steps")
            return explorer_result
            
        except Exception as e:
            logger.error(f"Error getting explorer data for checkpoint {checkpoint_id}: {str(e)}")
            return None
    
    def fetch_steps_by_checkpoint(self, thread_id: str, checkpoint_id: str) -> Optional[List[StepExplanation]]:
        """
        Fetch step data from a specific checkpoint
        
        Args:
            thread_id: The thread ID
            checkpoint_id: The specific checkpoint ID to fetch steps from
            
        Returns:
            List of StepExplanation objects if found, None otherwise
        """
        try:
            logger.info(f"Fetching steps for thread_id: {thread_id}, checkpoint_id: {checkpoint_id}")
            
            # Create config to get the state at specific checkpoint
            config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
            
            # Get the state from the agent
            state = self.agent.graph.get_state(config)
            
            if not state or not hasattr(state, 'values') or not state.values:
                logger.warning(f"No state found for thread_id: {thread_id}")
                return None
            
            # Check if this is the correct checkpoint
            current_checkpoint_id = None
            if hasattr(state, 'config') and state.config and 'configurable' in state.config:
                configurable = state.config['configurable']
                if 'checkpoint_id' in configurable:
                    current_checkpoint_id = str(configurable['checkpoint_id'])
            
            if current_checkpoint_id != checkpoint_id:
                logger.warning(f"Checkpoint mismatch. Expected: {checkpoint_id}, Found: {current_checkpoint_id}")
                # For now, we'll return the current steps even if checkpoint doesn't match
                # In the future, you might want to implement checkpoint history traversal
            
            # Extract steps from the state
            values = state.values
            steps_data = values.get("steps", [])
            
            if not steps_data:
                logger.info(f"No steps found in checkpoint {checkpoint_id}")
                return []
            
            # Convert steps data to StepExplanation objects
            steps = []
            for step_data in steps_data:
                if isinstance(step_data, dict):
                    step = StepExplanation(
                        id=step_data.get("id", 0),
                        type=step_data.get("type", "unknown"),
                        decision=step_data.get("decision", ""),
                        reasoning=step_data.get("reasoning", ""),
                        input=step_data.get("input", ""),
                        output=step_data.get("output", ""),
                        confidence=step_data.get("confidence", 0.0),
                        why_chosen=step_data.get("why_chosen", ""),
                        timestamp=step_data.get("timestamp", "")
                    )
                    steps.append(step)
            
            logger.info(f"Successfully fetched {len(steps)} steps from checkpoint {checkpoint_id}")
            return steps
            
        except Exception as e:
            logger.error(f"Error fetching steps for checkpoint {checkpoint_id}: {str(e)}")
            return None
    
    def fetch_step_summary(self, thread_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a summary of the step data from a specific checkpoint
        
        Args:
            thread_id: The thread ID
            checkpoint_id: The specific checkpoint ID
            
        Returns:
            Dictionary with step summary information
        """
        try:
            steps = self.fetch_steps_by_checkpoint(thread_id, checkpoint_id)
            
            if steps is None:
                return None
            
            if not steps:
                return {
                    "step_count": 0,
                    "has_steps": False,
                    "checkpoint_id": checkpoint_id,
                    "thread_id": thread_id
                }
            
            # Calculate summary statistics
            total_confidence = sum(step.confidence for step in steps)
            avg_confidence = total_confidence / len(steps) if steps else 0.0
            
            step_types = [step.type for step in steps]
            unique_types = list(set(step_types))
            
            return {
                "step_count": len(steps),
                "has_steps": True,
                "checkpoint_id": checkpoint_id,
                "thread_id": thread_id,
                "average_confidence": avg_confidence,
                "step_types": unique_types,
                "steps_preview": [
                    {
                        "id": step.id,
                        "type": step.type,
                        "decision": step.decision[:100] + "..." if len(step.decision) > 100 else step.decision
                    }
                    for step in steps[:3]  # First 3 steps as preview
                ]
            }
            
        except Exception as e:
            logger.error(f"Error fetching step summary for checkpoint {checkpoint_id}: {str(e)}")
            return None
