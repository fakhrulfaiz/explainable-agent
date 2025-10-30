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
    ChatThreadWithMessages,
    CreateChatRequest
)
from src.services.checkpoint_service import CheckpointService
from src.repositories.messages_repository import MessagesRepository
from src.services.message_management_service import MessageManagementService

logger = logging.getLogger(__name__)

class ChatHistoryService:
    """Service for managing chat history using repository pattern"""
    
    def __init__(self, 
                 chat_thread_repo: ChatThreadRepository,
                 checkpoint_service: CheckpointService,
                 messages_repo: MessagesRepository):
        self.chat_thread_repo = chat_thread_repo
        self.checkpoint_service = checkpoint_service
        self.messages_repo = messages_repo
    
    
    async def create_thread(self, request: CreateChatRequest) -> ChatThread:
    
        try:
            # Generate thread_id
            thread_id = str(uuid.uuid4())
            
            # Create thread object
            thread = ChatThread(
                thread_id=thread_id, 
                title=request.title or "New Chat",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Save thread first
            success = await self.chat_thread_repo.create_thread(thread)
            if not success:
                raise Exception("Failed to create chat thread in database")
            
            # Add initial message if provided (after thread is created)
            if request.initial_message:
                import time
                initial_msg = ChatMessage(
                    sender="user",
                    content=request.initial_message,
                    timestamp=datetime.now(),
                    thread_id=thread.thread_id,
                    message_id=int(time.time() * 1000000)  # Generate unique message_id
                )
                await self.messages_repo.add_message(initial_msg)
            
            logger.info(f"Created new chat thread: {thread_id}")
            
            # Verify thread was actually created
            try:
                created_thread = await self.chat_thread_repo.find_by_id(thread_id, "thread_id")
                logger.info(f"Thread verification - exists: {created_thread is not None}")
            except Exception as e:
                logger.error(f"Error verifying thread creation: {e}")
            
            return thread
            
        except Exception as e:
            logger.error(f"Error creating chat thread: {e}")
            raise Exception(f"Failed to create chat thread: {e}")
    
    async def get_thread(self, thread_id: str) -> Optional[ChatThreadWithMessages]:
        try:
            thread = await self.chat_thread_repo.find_by_thread_id(thread_id)
            if not thread:
                return None
            
            messages = await self.get_thread_messages(thread_id)
            return ChatThreadWithMessages(
                thread_id=thread.thread_id,
                title=thread.title,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                messages=messages
            )
        except Exception as e:
            logger.error(f"Error retrieving chat thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread: {e}")

    async def get_thread_messages(self, thread_id: str) -> List[ChatMessage]:
        try:
            messages = await self.messages_repo.get_all_messages_by_thread(thread_id)
            return messages
        except Exception as e:
            logger.error(f"Error retrieving chat thread messages {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread messages: {e}")

    
    

    async def update_message_flags(self, thread_id: str, message_id: int, *,
                                   needs_approval: Optional[bool] = None,
                                   approved: Optional[bool] = None,
                                   disapproved: Optional[bool] = None,
                                   is_error: Optional[bool] = None,
                                   is_feedback: Optional[bool] = None,
                                   has_timed_out: Optional[bool] = None,
                                   can_retry: Optional[bool] = None,
                                   retry_action: Optional[str] = None) -> bool:
        """Persistently update message approval/flag fields by message_id."""
        try:
            updates = {
                "thread_id": thread_id,
                "needs_approval": needs_approval,
                "approved": approved,
                "disapproved": disapproved,
                "is_error": is_error,
                "is_feedback": is_feedback,
                "has_timed_out": has_timed_out,
                "can_retry": can_retry,
                "retry_action": retry_action,
                "updated_at": datetime.now()
            }
            return await self.messages_repo.update_message_by_message_id(message_id, updates)
        except Exception as e:
            logger.error(f"Error updating message flags for thread {thread_id}, message {message_id}: {e}")
            raise Exception(f"Failed to update message flags: {e}")

    async def get_message_by_id(self, thread_id: str, message_id: int) -> Optional[ChatMessage]:
        """Get a specific message by its ID within a thread."""
        try:
            return await self.messages_repo.get_message_by_id(thread_id, message_id)
        except Exception as e:
            logger.error(f"Error retrieving message {message_id} from thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve message: {e}")
    
    async def get_all_threads(self, limit: int = 50, skip: int = 0) -> List[ChatThread]:
        try:
            return await self.chat_thread_repo.get_threads(limit=limit, skip=skip)
        except Exception as e:
            logger.error(f"Error retrieving chat threads: {e}")
            raise Exception(f"Failed to retrieve chat threads: {e}")

    async def get_all_threads_summary(self, limit: int = 50, skip: int = 0) -> List[ChatThreadSummary]:
        try:
            chat_threads = await self.chat_thread_repo.get_threads(limit=limit, skip=skip)

            thread_summaries = []
            for thread in chat_threads:
                message_count = await self.messages_repo.count_messages_by_thread(thread.thread_id)
                last_message_obj = await self.messages_repo.get_last_message_by_thread(thread.thread_id)
                last_message = last_message_obj.content if last_message_obj else None
                
                thread_summary = ChatThreadSummary(
                    thread_id=thread.thread_id,
                    title=thread.title,
                    created_at=thread.created_at,
                    updated_at=thread.updated_at,
                    last_message=last_message,
                    message_count=message_count
                )
                thread_summaries.append(thread_summary)
            return thread_summaries
        except Exception as e:
            logger.error(f"Error retrieving chat thread summaries: {e}")
            raise Exception(f"Failed to retrieve chat thread summaries: {e}")



    
    async def delete_thread(self, thread_id: str) -> bool:
    
        try:
            # Delete the thread
            thread_deleted = await self.chat_thread_repo.delete_thread(thread_id)
            await self.messages_repo.delete_messages_by_thread(thread_id)
            
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
