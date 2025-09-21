from pydantic import BaseModel, Field, validator, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
from .status_enums import ExecutionStatusType, ApprovalStatusType, validate_execution_status, validate_approval_status
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for query processing"""
    query: str = Field(..., min_length=1, max_length=1000, description="User query to process")


class QueryResponse(BaseModel):
    """Response model for query processing"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    timestamp: datetime


class StepExplanation(BaseModel):
    """Model for individual step explanations"""
    id: int
    type: str
    decision: str
    reasoning: str
    input: str
    output: str
    confidence: float
    why_chosen: str
    timestamp: str


class AgentInfo(BaseModel):
    """Information about available agents"""
    name: str
    description: str
    capabilities: List[str]


class SystemStatusResponse(BaseModel):
    """System status response"""
    status: str
    available_agents: List[AgentInfo]
    timestamp: datetime


class LogMetadata(BaseModel):
    """Metadata for log files"""
    filename: str
    created_at: datetime
    size: int


class LogListResponse(BaseModel):
    """Response model for listing logs"""
    logs: List[LogMetadata]
    total: int


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime


class FinalResult(BaseModel):
    """Final result model for completed agent execution"""
    summary: str
    details: str
    source: str
    inference: str
    extra_explanation: str


# Graph-based API models
class StartRequest(BaseModel):
    human_request: str = Field(..., min_length=1, max_length=1000, description="User request to process")
    thread_id: Optional[str] = Field(None, description="Optional thread ID for existing conversations")
    use_planning: bool = Field(True, description="Whether to use planning in agent execution")
    agent_type: str = Field("assistant", description="Type of agent to use: 'assistant' (routes to appropriate agent) or 'explainable' (direct to explainable agent)")


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="Thread ID of the graph execution to resume")
    review_action: ApprovalStatusType = Field(..., description="Human review action: 'approved', 'feedback', or 'cancelled'")
    human_comment: Optional[str] = Field(None, description="Optional human comment or feedback")
    
    @field_validator('review_action')
    def validate_review_action(cls, v):
        return validate_approval_status(v)


class GraphResponse(BaseModel):
    thread_id: str
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID")
    run_status: str = Field(..., description="Graph execution status: 'user_feedback', 'finished', or 'error'")
    assistant_response: Optional[str] = Field(None, description="Current assistant response or plan")
    query: Optional[str] = Field(None, description="Original user query/request")
    plan: Optional[str] = Field(None, description="Current execution plan")
    error: Optional[str] = Field(None, description="Error message if any")
    steps: Optional[List[StepExplanation]] = Field(None, description="Execution steps if completed")
    final_result: Optional[FinalResult] = Field(None, description="Final structured result if completed")
    total_time: Optional[float] = Field(None, description="Total execution time if completed")
    overall_confidence: Optional[float] = Field(None, description="Overall confidence score if completed")


class GraphStatusResponse(BaseModel):

    thread_id: str
    execution_status: ExecutionStatusType = Field(..., description="Graph execution state: 'user_feedback', 'running', or 'finished'")
    next_nodes: List[str] = Field(default_factory=list, description="Next nodes to execute")
    plan: str = Field(default="", description="Current execution plan")
    step_count: int = Field(default=0, description="Number of steps completed")
    approval_status: ApprovalStatusType = Field(default="unknown", description="Agent approval state: 'approved', 'feedback', or 'cancelled'")
    
    @field_validator('execution_status')
    def validate_execution_status(cls, v):
        return validate_execution_status(v)
    
    @field_validator('approval_status')
    def validate_approval_status(cls, v):
        return validate_approval_status(v) 