from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="Thread ID of the graph execution to resume")
    review_action: str = Field(..., description="Action to take: 'approved', 'feedback', or 'cancelled'")
    human_comment: Optional[str] = Field(None, description="Optional human comment or feedback")


class GraphResponse(BaseModel):
    thread_id: str
    run_status: str = Field(..., description="Status: 'user_feedback', 'finished', or 'error'")
    assistant_response: Optional[str] = Field(None, description="Current assistant response or plan")
    plan: Optional[str] = Field(None, description="Current execution plan")
    error: Optional[str] = Field(None, description="Error message if any")
    steps: Optional[List[StepExplanation]] = Field(None, description="Execution steps if completed")
    final_result: Optional[FinalResult] = Field(None, description="Final structured result if completed")
    total_time: Optional[float] = Field(None, description="Total execution time if completed")
    overall_confidence: Optional[float] = Field(None, description="Overall confidence score if completed") 