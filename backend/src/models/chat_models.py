from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from bson import ObjectId


class ChatMessage(BaseModel):
    """Individual chat message"""
    sender: Literal["user", "assistant"] = Field(..., description="Message sender")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    message_type: Literal["message", "explorer"] = Field(default="message", description="Message type - message or explorer")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID for explorer messages to fetch step data")
    
    # Additional fields from frontend Message interface
    message_id: Optional[int] = Field(None, description="Message ID from frontend")
    needs_approval: Optional[bool] = Field(None, description="Whether message needs approval")
    approved: Optional[bool] = Field(None, description="Whether message is approved")
    disapproved: Optional[bool] = Field(None, description="Whether message is disapproved")
    is_error: Optional[bool] = Field(None, description="Whether message is an error")
    is_feedback: Optional[bool] = Field(None, description="Whether message is feedback")
    has_timed_out: Optional[bool] = Field(None, description="Whether message has timed out")
    can_retry: Optional[bool] = Field(None, description="Whether message can be retried")
    retry_action: Optional[Literal["approve", "feedback", "cancel"]] = Field(None, description="Retry action type")
    thread_id_ref: Optional[str] = Field(None, description="Thread ID reference from frontend")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatThread(BaseModel):
    """Chat thread/conversation"""
    thread_id: str = Field(..., description="Unique thread identifier")
    title: Optional[str] = Field(None, description="Chat thread title")
    messages: List[ChatMessage] = Field(default_factory=list, description="Chat messages")
    created_at: datetime = Field(default_factory=datetime.now, description="Thread creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatThreadSummary(BaseModel):
    """Summary view of chat thread for listing"""
    thread_id: str = Field(..., description="Unique thread identifier")
    title: Optional[str] = Field(None, description="Chat thread title")
    last_message: Optional[str] = Field(None, description="Last message preview")
    message_count: int = Field(0, description="Total message count")
    created_at: datetime = Field(..., description="Thread creation time")
    updated_at: datetime = Field(..., description="Last update time")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CreateChatRequest(BaseModel):
    """Request to create new chat thread"""
    title: Optional[str] = Field(None, description="Optional thread title")
    initial_message: Optional[str] = Field(None, description="Optional initial user message")


class AddMessageRequest(BaseModel):
    """Request to add message to existing thread"""
    thread_id: str = Field(..., description="Thread ID")
    sender: Literal["user", "assistant"] = Field(..., description="Message sender")
    content: str = Field(..., description="Message content")
    message_type: Literal["message", "explorer"] = Field(default="message", description="Message type - message or explorer")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID for explorer messages to fetch step data")
    
    # Additional fields from frontend Message interface
    message_id: Optional[int] = Field(None, description="Message ID from frontend")
    needs_approval: Optional[bool] = Field(None, description="Whether message needs approval")
    approved: Optional[bool] = Field(None, description="Whether message is approved")
    disapproved: Optional[bool] = Field(None, description="Whether message is disapproved")
    is_error: Optional[bool] = Field(None, description="Whether message is an error")
    is_feedback: Optional[bool] = Field(None, description="Whether message is feedback")
    has_timed_out: Optional[bool] = Field(None, description="Whether message has timed out")
    can_retry: Optional[bool] = Field(None, description="Whether message can be retried")
    retry_action: Optional[Literal["approve", "feedback", "cancel"]] = Field(None, description="Retry action type")
    thread_id_ref: Optional[str] = Field(None, description="Thread ID reference from frontend")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class ChatHistoryResponse(BaseModel):
    """Response containing chat thread data"""
    success: bool = Field(..., description="Request success status")
    data: Optional[ChatThread] = Field(None, description="Chat thread data")
    message: str = Field(..., description="Response message")


class ChatListResponse(BaseModel):
    """Response containing list of chat threads"""
    success: bool = Field(..., description="Request success status")
    data: List[ChatThreadSummary] = Field(default_factory=list, description="List of chat threads")
    message: str = Field(..., description="Response message")
    total: int = Field(0, description="Total number of threads")
