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
    CreateChatRequest,
    AddMessageRequest
)
from src.services.checkpoint_service import CheckpointService
from src.repositories.messages_repository import MessagesRepository

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
            
            # Add initial message if provided
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
            
            # Save using repository
            success = await self.chat_thread_repo.create_thread(thread)
            if not success:
                raise Exception("Failed to create chat thread in database")
            
            logger.info(f"Created new chat thread: {thread_id}")
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
            print(f"Thread {thread_id}: messages = {messages}")
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

    
    
    async def add_message(self, request: AddMessageRequest) -> bool:
        
        try:
            # Ensure message_id is provided - generate one if not provided
            message_id = request.message_id
            if message_id is None:
                import time
                message_id = int(time.time() * 1000000)  # Microsecond precision timestamp
                logger.warning(f"message_id was None, generated: {message_id}")
            
            message = ChatMessage(
                sender=request.sender,
                content=request.content,
                timestamp=datetime.now(),
                message_type=request.message_type,
                checkpoint_id=request.checkpoint_id,
                message_id=message_id,
                needs_approval=request.needs_approval,
                approved=request.approved,
                disapproved=request.disapproved,
                is_error=request.is_error,
                is_feedback=request.is_feedback,
                has_timed_out=request.has_timed_out,
                can_retry=request.can_retry,
                retry_action=request.retry_action,
                thread_id=request.thread_id
            )
            
            success = await self.messages_repo.add_message(message)
            if success:
                logger.info(f"Added message to thread {request.thread_id}")
            else:
                logger.warning(f"Thread {request.thread_id} not found")
            
            return success
                
        except Exception as e:
            logger.error(f"Error adding message to thread {request.thread_id}: {e}")
            raise Exception(f"Failed to add message: {e}")
    
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
                print(f"Thread {thread.thread_id}: message_count = {message_count}")
                last_message_obj = await self.messages_repo.get_last_message_by_thread(thread.thread_id)
                print(f"Thread {thread.thread_id}: last_message_obj = {last_message_obj}")
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
