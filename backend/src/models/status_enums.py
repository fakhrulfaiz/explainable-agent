from enum import Enum
from typing import Literal


class ExecutionStatus(str, Enum):

    USER_FEEDBACK = "user_feedback"  # Waiting for human approval/feedback
    RUNNING = "running"             # Graph is actively executing
    FINISHED = "finished"           # Graph execution completed
    ERROR = "error"                 # Graph execution failed


class ApprovalStatus(str, Enum):
   
    APPROVED = "approved"           # Human approved the plan
    FEEDBACK = "feedback"          # Human provided feedback for revision
    CANCELLED = "cancelled"        # Human cancelled the operation
    UNKNOWN = "unknown"            # Status not yet determined


class SystemStatus(str, Enum):
  
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


ExecutionStatusType = Literal["user_feedback", "running", "finished", "error"]
ApprovalStatusType = Literal["approved", "feedback", "cancelled", "unknown"]
SystemStatusType = Literal["healthy", "degraded", "down"]


def validate_execution_status(status: str) -> ExecutionStatusType:
    try:
        ExecutionStatus(status)
        return status  # type: ignore
    except ValueError:
        raise ValueError(f"Invalid execution status: {status}. Must be one of {[s.value for s in ExecutionStatus]}")


def validate_approval_status(status: str) -> ApprovalStatusType:
    """Validate and return approval status"""
    try:
        ApprovalStatus(status)
        return status  # type: ignore
    except ValueError:
        raise ValueError(f"Invalid approval status: {status}. Must be one of {[s.value for s in ApprovalStatus]}")


def get_execution_status_description(status: ExecutionStatusType) -> str:

    descriptions = {
        ExecutionStatus.USER_FEEDBACK: "Waiting for human approval or feedback",
        ExecutionStatus.RUNNING: "Graph is actively executing",
        ExecutionStatus.FINISHED: "Graph execution completed successfully",
        ExecutionStatus.ERROR: "Graph execution failed with an error"
    }
    return descriptions.get(ExecutionStatus(status), "Unknown status")


def get_approval_status_description(status: ApprovalStatusType) -> str:
    """Get human-readable description of approval status"""
    descriptions = {
        ApprovalStatus.APPROVED: "Human approved the plan",
        ApprovalStatus.FEEDBACK: "Human provided feedback for revision",
        ApprovalStatus.CANCELLED: "Human cancelled the operation", 
        ApprovalStatus.UNKNOWN: "Approval status not yet determined"
    }
    return descriptions.get(ApprovalStatus(status), "Unknown status")
