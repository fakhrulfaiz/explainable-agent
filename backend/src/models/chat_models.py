from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from bson import ObjectId
import warnings


class MessageContent(BaseModel):
    """Individual content block for a message"""
    message_id: int = Field(..., description="Foreign key to messages collection")
    block_id: str = Field(..., description="Unique block identifier")
    type: str = Field(..., description="Block type: text, tool_calls, explorer, visualizations")
    needs_approval: bool = Field(default=False, description="Whether this block needs approval")
    message_status: Optional[Literal["pending", "approved", "rejected", "error", "timeout"]] = Field(default=None, description="Status of this content block")
    data: Dict[str, Any] = Field(..., description="Block data content")
    created_at: datetime = Field(default_factory=datetime.now, description="Block creation timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatMessage(BaseModel):
    """Individual chat message"""
    thread_id: Optional[str] = Field(None, description="Thread ID for this message")
    sender: Literal["user", "assistant"] = Field(..., description="Message sender")
    content: List[Dict[str, Any]] = Field(default_factory=list, description="Message content blocks (loaded from message_content collection)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    message_type: Optional[Literal["message", "explorer", "visualization", "structured"]] = Field(default="structured", description="Message type")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID for explorer messages to fetch step data")
    user_id: Optional[str] = Field(None, description="User ID who owns this message")
    
    # Message ID
    message_id: int = Field(..., description="Message ID")
    
    # Message status
    message_status: Optional[Literal["pending", "approved", "rejected", "error", "timeout"]] = Field(None, description="Message status")

    @validator('message_type', pre=True, always=True)
    def validate_message_type(cls, v, values):
        """Validate and auto-determine message_type based on content"""
        content = values.get('content', [])
        
        # If content exists and has blocks, determine type from blocks
        if content and isinstance(content, list) and len(content) > 0:
            return "structured"
        
        # Fallback to provided value or default
        return v or "structured"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatThread(BaseModel):
    """Chat thread/conversation"""
    thread_id: str = Field(..., description="Unique thread identifier")
    title: Optional[str] = Field(None, description="Chat thread title")
    created_at: datetime = Field(default_factory=datetime.now, description="Thread creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    user_id: Optional[str] = Field(None, description="User ID who owns this thread")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ChatThreadWithMessages(ChatThread):
    """Chat thread with messages"""
    messages: List[ChatMessage] = Field(..., description="Messages")
    # user_id is inherited from ChatThread


class ChatThreadSummary(BaseModel):
    """Summary view of chat thread for listing"""
    # Chat thread properties at top level
    thread_id: str = Field(..., description="Thread ID")
    title: str = Field(..., description="Thread title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_message: Optional[str] = Field(None, description="Last message preview")
    message_count: int = Field(0, description="Total message count for thread")
    
    
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
    content: List[Dict[str, Any]] = Field(default_factory=list, description="Message content blocks")
    message_type: Optional[Literal["message", "explorer", "visualization", "structured"]] = Field(default="structured", description="Message type")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID for explorer messages to fetch step data")
    
    # Message ID
    message_id: int = Field(..., description="Message ID")
    
    # Message status
    message_status: Optional[Literal["pending", "approved", "rejected", "error", "timeout"]] = Field(None, description="Message status")
    
    metadata: Optional[dict] = Field(None, description="Additional metadata")

    @validator('message_type', pre=True, always=True)
    def validate_message_type(cls, v, values):
        """Validate and auto-determine message_type based on content"""
        content = values.get('content', [])
        
        # If content exists and has blocks, determine type from blocks
        if content and isinstance(content, list) and len(content) > 0:
            return "structured"
        
        # Fallback to provided value or default
        return v or "structured"


class ChatHistoryResponse(BaseModel):
    """Response containing chat thread data"""
    success: bool = Field(..., description="Request success status")
    data: Optional[ChatThreadWithMessages] = Field(None, description="Chat thread data with messages")
    message: str = Field(..., description="Response message")


class ChatListResponse(BaseModel):
    """Response containing list of chat threads"""
    success: bool = Field(..., description="Request success status")
    data: List[ChatThreadSummary] = Field(default_factory=list, description="List of chat threads")
    message: str = Field(..., description="Response message")
    total: int = Field(0, description="Total number of threads")


class CheckpointSummary(BaseModel):
    """Summary view of a checkpoint for listing"""
    checkpoint_id: str = Field(..., description="Checkpoint ID")
    thread_id: str = Field(..., description="Thread ID associated with this checkpoint")
    timestamp: datetime = Field(..., description="Checkpoint timestamp")
    message_type: Optional[Literal["message", "explorer", "visualization", "structured"]] = Field(None, description="Message type")
    message_id: int = Field(..., description="Message ID associated with this checkpoint")
    query: Optional[str] = Field(None, description="User query from checkpoint state")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CheckpointListResponse(BaseModel):
    """Response containing list of checkpoints"""
    success: bool = Field(..., description="Request success status")
    data: List[CheckpointSummary] = Field(default_factory=list, description="List of checkpoints")
    message: str = Field(..., description="Response message")
    total: int = Field(0, description="Total number of checkpoints")