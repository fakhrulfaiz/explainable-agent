from typing import List, Optional
from datetime import datetime
import uuid
import logging

from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from src.models.chat_models import (
    ChatThread, 
    ChatMessage, 
    ChatThreadSummary,
    CreateChatRequest,
    AddMessageRequest
)
from src.services.checkpoint_service import CheckpointService

logger = logging.getLogger(__name__)

class ChatHistoryService:
    """Service for managing chat history using repository pattern"""
    
    def __init__(self, 
                 chat_thread_repo: ChatThreadRepository,
                 checkpoint_service: CheckpointService):
        self.chat_thread_repo = chat_thread_repo
        self.checkpoint_service = checkpoint_service
    
    
    async def create_thread(self, request: CreateChatRequest) -> ChatThread:
    
        try:
            # Generate thread_id
            thread_id = str(uuid.uuid4())
            
            # Create thread object
            thread = ChatThread(
                thread_id=thread_id,
                title=request.title or "New Chat",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Add initial message if provided
            if request.initial_message:
                initial_msg = ChatMessage(
                    sender="user",
                    content=request.initial_message,
                    timestamp=datetime.now()
                )
                thread.messages.append(initial_msg)
            
            # Save using repository
            success = await self.chat_thread_repo.create_thread(thread)
            if not success:
                raise Exception("Failed to create chat thread in database")
            
            logger.info(f"Created new chat thread: {thread_id}")
            return thread
            
        except Exception as e:
            logger.error(f"Error creating chat thread: {e}")
            raise Exception(f"Failed to create chat thread: {e}")
    
    async def get_thread(self, thread_id: str) -> Optional[ChatThread]:
    
        try:
            return await self.chat_thread_repo.find_by_thread_id(thread_id)
        except Exception as e:
            logger.error(f"Error retrieving chat thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread: {e}")
    
    async def add_message(self, request: AddMessageRequest) -> bool:

        try:
            message = ChatMessage(
                sender=request.sender,
                content=request.content,
                timestamp=datetime.now(),
                message_type=request.message_type,
                checkpoint_id=request.checkpoint_id
            )
            
            success = await self.chat_thread_repo.add_message_to_thread(request.thread_id, message)
            if success:
                logger.info(f"Added message to thread {request.thread_id}")
            else:
                logger.warning(f"Thread {request.thread_id} not found")
            
            return success
                
        except Exception as e:
            logger.error(f"Error adding message to thread {request.thread_id}: {e}")
            raise Exception(f"Failed to add message: {e}")
    
    async def get_all_threads(self, limit: int = 50, skip: int = 0) -> List[ChatThreadSummary]:
        try:
            return await self.chat_thread_repo.get_thread_summaries(limit=limit, skip=skip)
        except Exception as e:
            logger.error(f"Error retrieving chat threads: {e}")
            raise Exception(f"Failed to retrieve chat threads: {e}")
    
    async def delete_thread(self, thread_id: str) -> bool:
    
        try:
            # Delete the thread
            thread_deleted = await self.chat_thread_repo.delete_thread(thread_id)
            
            if thread_deleted:
                logger.info(f"Deleted chat thread: {thread_id}")
                
                # Clean up associated checkpoint data
                try:
                    checkpoint_result = await self.checkpoint_service.delete_all_thread_data(thread_id)
                    total_deleted = checkpoint_result.get('total_deleted', 0)
                    if total_deleted > 0:
                        logger.info(f"Deleted {total_deleted} checkpoint records for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete checkpoint data for thread {thread_id}: {e}")
                    # Don't fail the whole operation if checkpoint cleanup fails
                
                return True
            else:
                logger.warning(f"Thread {thread_id} not found for deletion")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting chat thread {thread_id}: {e}")
            raise Exception(f"Failed to delete chat thread: {e}")
    
    async def update_thread_title(self, thread_id: str, title: str) -> bool:
    
        try:
            success = await self.chat_thread_repo.update_thread_title(thread_id, title)
            if success:
                logger.info(f"Updated title for thread {thread_id}")
            else:
                logger.warning(f"Thread {thread_id} not found for title update")
            return success
        except Exception as e:
            logger.error(f"Error updating thread title {thread_id}: {e}")
            raise Exception(f"Failed to update thread title: {e}")
    
    async def get_thread_count(self) -> int:
    
        try:
            return await self.chat_thread_repo.count_threads()
        except Exception as e:
            logger.error(f"Error counting chat threads: {e}")
            return 0
