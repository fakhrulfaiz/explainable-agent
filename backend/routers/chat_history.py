from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional, Literal, Annotated
from src.services.chat_history_service import ChatHistoryService
from src.services.message_management_service import MessageManagementService
from src.repositories.dependencies import get_chat_history_service, get_message_management_service, get_messages_repository
from src.repositories.messages_repository import MessagesRepository
from src.models.chat_models import (
    ChatHistoryResponse,
    ChatListResponse,
    CreateChatRequest,
    ChatThread,
    CheckpointSummary,
    CheckpointListResponse
)
from src.middleware.auth import get_current_user
from src.models.supabase_user import SupabaseUser
from src.services.explainable_agent import ExplainableAgent
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
    chat_service: ChatHistoryService = Depends(get_chat_history_service),
    current_user: SupabaseUser = Depends(get_current_user)
):
    try:
        user_id = current_user.user_id
        logger.info(f"Creating chat thread with title: '{request.title}', user_id: {user_id}")
        
        thread = await chat_service.create_thread(request, user_id=user_id)
        logger.info(f"Thread created successfully: {thread.thread_id}")
        
        # Convert ChatThread to ChatThreadWithMessages by getting the full thread data
        thread_with_messages = await chat_service.get_thread(thread.thread_id)
        logger.info(f"Retrieved thread with messages: {thread_with_messages is not None}")
        
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
    chat_service: ChatHistoryService = Depends(get_chat_history_service),
    current_user: SupabaseUser = Depends(get_current_user)
):
  
    try:
        user_id = current_user.user_id
        logger.info(f"Retrieving threads for user_id: {user_id}")
        
        threads = await chat_service.get_all_threads_summary(limit=limit, skip=skip, user_id=user_id)
        total = await chat_service.get_thread_count(user_id=user_id)
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
    chat_service: ChatHistoryService = Depends(get_chat_history_service),
    current_user: SupabaseUser = Depends(get_current_user)
):
    try:
        user_id = current_user.user_id
        logger.info(f"Retrieving thread {thread_id} for user_id: {user_id}")
        
        thread = await chat_service.get_thread(thread_id, user_id=user_id)
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

# Legacy endpoint removed - use block-level approval endpoint instead
# PUT /thread/{thread_id}/message/{message_id}/block/{block_id}/approval


@router.post("/thread/{thread_id}/restore", response_model=ChatHistoryResponse)
async def restore_chat_thread(
    thread_id: str,
    chat_service: ChatHistoryService = Depends(get_chat_history_service),
    current_user: SupabaseUser = Depends(get_current_user)
):
    """
    Restore a chat thread for continuing conversation.
    This endpoint returns the full chat history that can be used to restore the conversation context.
    """
    try:
        user_id = current_user.user_id
        logger.info(f"Restoring chat thread {thread_id} with user_id: {user_id}")
        
        thread = await chat_service.get_thread(thread_id, user_id=user_id)
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


# Message Status Synchronization Endpoints

class MessageStatusUpdateRequest(BaseModel):
    """Update message-level status (deprecated - use block-level status instead)"""
    message_status: Optional[Literal["pending", "approved", "rejected", "error", "timeout"]] = None


@router.put("/thread/{thread_id}/message/{message_id}/status", response_model=dict)
async def update_message_status(
    thread_id: str,
    message_id: int,
    request: MessageStatusUpdateRequest,
    message_service: MessageManagementService = Depends(get_message_management_service)
):
    """
    Update message-level status (deprecated - use block-level approval endpoint instead).
    This endpoint is kept for backward compatibility but should not be used for new code.
    """
    try:
        # Convert request to dict, excluding None values
        status_updates = {k: v for k, v in request.dict().items() 
                         if v is not None}
        
        if not status_updates:
            raise HTTPException(status_code=400, detail="No valid status updates provided")
        
        success = await message_service.update_message_status(
            thread_id=thread_id,
            message_id=message_id,
            **status_updates
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "success": True,
            "message": "Message status updated successfully",
            "updated_fields": list(status_updates.keys())
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating message status for thread {thread_id}, message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thread/{thread_id}/message/{message_id}/error", response_model=dict)
async def mark_message_error(
    thread_id: str,
    message_id: int,
    error_message: Optional[str] = None,
    message_service: MessageManagementService = Depends(get_message_management_service)
):
    """
    Mark a message as having an error. This is useful for handling
    failed operations or timeout scenarios.
    """
    try:
        success = await message_service.mark_message_error(
            thread_id=thread_id,
            message_id=message_id,
            error_message=error_message
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "success": True,
            "message": "Message marked as error successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking message as error for thread {thread_id}, message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thread/{thread_id}/messages/status", response_model=dict)
async def get_messages_status(
    thread_id: str,
    message_service: MessageManagementService = Depends(get_message_management_service)
):
    """
    Get status information for all messages in a thread. This helps
    the frontend sync its local state with the backend.
    """
    try:
        messages = await message_service.get_thread_messages(thread_id)
        
        status_info = []
        for message in messages:
            status_info.append({
                "message_id": message.message_id,
                "sender": message.sender,
                "timestamp": message.timestamp.isoformat(),
                "message_status": message.message_status,
                "message_type": message.message_type,
                "checkpoint_id": message.checkpoint_id,
                "has_content_blocks": bool(message.content and len(message.content) > 0)
            })
        
        return {
            "success": True,
            "thread_id": thread_id,
            "message_count": len(status_info),
            "messages": status_info
        }
    except Exception as e:
        logger.error(f"Error getting message status for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BlockStatusUpdateRequest(BaseModel):
    """Request to update block-level status"""
    needsApproval: Optional[bool] = None
    messageStatus: Optional[Literal["pending", "approved", "rejected", "error", "timeout"]] = None


@router.put("/thread/{thread_id}/message/{message_id}/block/{block_id}/approval", response_model=dict)
async def update_block_approval(
    thread_id: str,
    message_id: int,
    block_id: str,
    request: BlockStatusUpdateRequest,
    message_service: MessageManagementService = Depends(get_message_management_service)
):
    """
    Update block-level approval status. This endpoint allows the frontend to update
    individual block approval status within a message's content_blocks.
    """
    try:
        # Convert request to dict, excluding None values
        status_updates = {k: v for k, v in request.dict().items() 
                         if v is not None}
        
        if not status_updates:
            raise HTTPException(status_code=400, detail="No valid block status updates provided")
        
        success = await message_service.update_block_status(
            thread_id=thread_id,
            message_id=message_id,
            block_id=block_id,
            **status_updates
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Block not found or not modified")
        
        return {
            "success": True,
            "message": "Block status updated successfully",
            "updated_fields": list(status_updates.keys())
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating block status for thread {thread_id}, message {message_id}, block {block_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_explainable_agent(request: Request) -> ExplainableAgent:
    """Dependency to get ExplainableAgent from app state"""
    return request.app.state.explainable_agent


@router.get("/checkpoints", response_model=CheckpointListResponse)
async def get_checkpoints(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Number of checkpoints to return"),
    skip: int = Query(0, ge=0, description="Number of checkpoints to skip"),
    messages_repo: MessagesRepository = Depends(get_messages_repository),
    current_user: SupabaseUser = Depends(get_current_user)
):
    """Get all checkpoints for the current user across all threads"""
    try:
        user_id = current_user.user_id
        logger.info(f"Retrieving checkpoints for user_id: {user_id}")
        
        # Get checkpoints and total count in parallel
        checkpoints_data = await messages_repo.get_checkpoints_by_user_id(
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        total = await messages_repo.count_checkpoints_by_user_id(user_id=user_id)
        
        # Convert dict results to CheckpointSummary models and fetch query from state
        agent = get_explainable_agent(request)
        checkpoints = []
        for item in checkpoints_data:
            query = None
            # Try to get query from checkpoint state
            try:
                config = {"configurable": {"thread_id": item["thread_id"], "checkpoint_id": item["checkpoint_id"]}}
                state = agent.graph.get_state(config)
                if state and hasattr(state, 'values') and state.values:
                    query = state.values.get("query")
            except Exception as e:
                logger.debug(f"Could not fetch query for checkpoint {item['checkpoint_id']}: {e}")
                # Continue without query if state fetch fails
            
            checkpoints.append(
                CheckpointSummary(
                    checkpoint_id=item["checkpoint_id"],
                    thread_id=item["thread_id"],
                    timestamp=item["timestamp"],
                    message_type=item.get("message_type"),
                    message_id=item["message_id"],
                    query=query
                )
            )
        
        return CheckpointListResponse(
            success=True,
            data=checkpoints,
            message=f"Retrieved {len(checkpoints)} checkpoints",
            total=total
        )
    except Exception as e:
        logger.error(f"Error retrieving checkpoints for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))