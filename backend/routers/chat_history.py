from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from src.services.chat_history_service import ChatHistoryService
from src.repositories.dependencies import get_chat_history_service
from src.models.chat_models import (
    ChatHistoryResponse,
    ChatListResponse,
    CreateChatRequest,
    AddMessageRequest,
    ChatThread
)
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat-history",
    tags=["chat-history"]
)


@router.post("/create", response_model=ChatHistoryResponse)
async def create_chat_thread(
    request: CreateChatRequest,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    try:
        thread = await chat_service.create_thread(request)
        # Convert ChatThread to ChatThreadWithMessages by getting the full thread data
        thread_with_messages = await chat_service.get_thread(thread.thread_id)
        return ChatHistoryResponse(
            success=True,
            data=thread_with_messages,
            message="Chat thread created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating chat thread: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads", response_model=ChatListResponse)
async def get_all_chat_threads(
    limit: int = Query(50, ge=1, le=100, description="Number of threads to return"),
    skip: int = Query(0, ge=0, description="Number of threads to skip"),
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
  
    try:
        threads = await chat_service.get_all_threads_summary(limit=limit, skip=skip)
        if threads:
            print("/last message", threads[0].last_message)
        total = await chat_service.get_thread_count()
        return ChatListResponse(
            success=True,
            data=threads,
            message=f"Retrieved {len(threads)} chat threads",
            total=total
        )
    except Exception as e:
        logger.error(f"Error retrieving chat threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thread/{thread_id}", response_model=ChatHistoryResponse)
async def get_chat_thread(
    thread_id: str,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    try:
        thread = await chat_service.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        
        return ChatHistoryResponse(
            success=True,
            data=thread,
            message="Chat thread retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-message", response_model=dict)
async def add_message_to_thread(
    request: AddMessageRequest,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    """Add a message to an existing chat thread"""
    try:
        success = await chat_service.add_message(request)
        if not success:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        
        return {
            "success": True,
            "message": "Message added successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message to thread {request.thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/thread/{thread_id}/title", response_model=dict)
async def update_thread_title(
    thread_id: str, 
    title: str,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    """Update the title of a chat thread"""
    try:
        success = await chat_service.update_thread_title(thread_id, title)
        if not success:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        
        return {
            "success": True,
            "message": "Thread title updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating thread title {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/thread/{thread_id}", response_model=dict)
async def delete_chat_thread(
    thread_id: str,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    """Delete a chat thread"""
    try:
        success = await chat_service.delete_thread(thread_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        
        return {
            "success": True,
            "message": "Chat thread deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class UpdateMessageFlagsRequest(BaseModel):
    message_id: int
    needs_approval: Optional[bool] = None
    approved: Optional[bool] = None
    disapproved: Optional[bool] = None
    is_error: Optional[bool] = None
    is_feedback: Optional[bool] = None
    has_timed_out: Optional[bool] = None
    can_retry: Optional[bool] = None
    retry_action: Optional[str] = None


@router.put("/thread/{thread_id}/message/flags", response_model=dict)
async def update_message_flags(
    thread_id: str,
    request: UpdateMessageFlagsRequest,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    try:
        success = await chat_service.update_message_flags(
            thread_id=thread_id,
            message_id=request.message_id,
            needs_approval=request.needs_approval,
            approved=request.approved,
            disapproved=request.disapproved,
            is_error=request.is_error,
            is_feedback=request.is_feedback,
            has_timed_out=request.has_timed_out,
            can_retry=request.can_retry,
            retry_action=request.retry_action,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Message not found or not modified")
        
        # Get the updated message to return it
        updated_message = await chat_service.get_message_by_id(thread_id, request.message_id)
        
        return {
            "success": True, 
            "message": "Message flags updated",
            "updated_message": updated_message
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating message flags for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thread/{thread_id}/restore", response_model=ChatHistoryResponse)
async def restore_chat_thread(
    thread_id: str,
    chat_service: ChatHistoryService = Depends(get_chat_history_service)
):
    """
    Restore a chat thread for continuing conversation.
    This endpoint returns the full chat history that can be used to restore the conversation context.
    """
    try:
        thread = await chat_service.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        
        return ChatHistoryResponse(
            success=True,
            data=thread,
            message=f"Chat thread restored with {len(thread.messages)} messages"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring chat thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
