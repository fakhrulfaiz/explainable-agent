from typing import List, Optional
from datetime import datetime
import uuid
import logging

from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from src.repositories.message_content_repository import MessageContentRepository
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
                 messages_repo: MessagesRepository,
                 message_content_repo: Optional[MessageContentRepository] = None):
        self.chat_thread_repo = chat_thread_repo
        self.checkpoint_service = checkpoint_service
        self.messages_repo = messages_repo
        self.message_content_repo = message_content_repo
    
    
    async def create_thread(self, request: CreateChatRequest, user_id: Optional[str] = None) -> ChatThread:
    
        try:
            # Generate thread_id
            thread_id = str(uuid.uuid4())
            
            # Create thread object
            thread = ChatThread(
                thread_id=thread_id, 
                title=request.title or "New Chat",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                user_id=user_id  # Include user_id
            )
            
            if user_id:
                logger.info(f"Creating new chat thread: {thread_id} with user_id: {user_id}")
            
            # Save thread first
            success = await self.chat_thread_repo.create_thread(thread)
            if not success:
                raise Exception("Failed to create chat thread in database")
        
            
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
    
    async def get_thread(self, thread_id: str, user_id: Optional[str] = None) -> Optional[ChatThreadWithMessages]:
        try:
            thread = await self.chat_thread_repo.find_by_thread_id(thread_id, user_id=user_id)
            if not thread:
                return None
            
            messages = await self.get_thread_messages(thread_id)
            return ChatThreadWithMessages(
                thread_id=thread.thread_id,
                title=thread.title,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                user_id=thread.user_id,
                messages=messages
            )
        except Exception as e:
            logger.error(f"Error retrieving chat thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread: {e}")

    async def get_thread_messages(self, thread_id: str) -> List[ChatMessage]:
        try:
            messages = await self.messages_repo.get_all_messages_by_thread(thread_id)
            
            # Load content blocks for each message if message_content_repo is available
            if self.message_content_repo:
                for message in messages:
                    if message.message_id:
                        try:
                            content_blocks = await self.message_content_repo.get_blocks_by_message_id(message.message_id)
                            message.content = content_blocks
                        except Exception as e:
                            logger.warning(f"Failed to load content blocks for message {message.message_id}: {e}")
                            message.content = []
            
            return messages
        except Exception as e:
            logger.error(f"Error retrieving chat thread messages {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread messages: {e}")

    
    

    # Legacy update_message_flags method removed - use block-level approval instead

    async def get_message_by_id(self, thread_id: str, message_id: int) -> Optional[ChatMessage]:
        """Get a specific message by its ID within a thread."""
        try:
            return await self.messages_repo.get_message_by_id(thread_id, message_id)
        except Exception as e:
            logger.error(f"Error retrieving message {message_id} from thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve message: {e}")
    
    async def get_all_threads(self, limit: int = 50, skip: int = 0, user_id: Optional[str] = None) -> List[ChatThread]:
        try:
            return await self.chat_thread_repo.get_threads(limit=limit, skip=skip, user_id=user_id)
        except Exception as e:
            logger.error(f"Error retrieving chat threads: {e}")
            raise Exception(f"Failed to retrieve chat threads: {e}")

    async def get_all_threads_summary(self, limit: int = 50, skip: int = 0, user_id: Optional[str] = None) -> List[ChatThreadSummary]:
        try:
            chat_threads = await self.chat_thread_repo.get_threads(limit=limit, skip=skip, user_id=user_id)

            thread_summaries = []
            for thread in chat_threads:
                message_count = await self.messages_repo.count_messages_by_thread(thread.thread_id)
                last_message_obj = await self.messages_repo.get_last_message_by_thread(thread.thread_id)
                
                # Extract text preview from content blocks
                last_message = None
                if last_message_obj:
                    # Load content blocks if message_content_repo is available
                    if self.message_content_repo and last_message_obj.message_id:
                        try:
                            content_blocks = await self.message_content_repo.get_blocks_by_message_id(last_message_obj.message_id)
                            last_message_obj.content = content_blocks
                        except Exception as e:
                            logger.warning(f"Failed to load content blocks for message {last_message_obj.message_id}: {e}")
                            last_message_obj.content = []
                    
                    # Extract text from content blocks
                    if last_message_obj.content:
                        text_parts = []
                        for block in last_message_obj.content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text = block.get('data', {}).get('text', '')
                                if text:
                                    text_parts.append(text)
                        
                        if text_parts:
                            # Join all text parts and truncate to 100 chars for preview
                            preview = ' '.join(text_parts)
                            last_message = preview[:100] + '...' if len(preview) > 100 else preview
                
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
            # First, get all message IDs for this thread to clean up message_content
            messages = await self.messages_repo.get_all_messages_by_thread(thread_id)
            message_ids = [msg.message_id for msg in messages if msg.message_id]
            
            # Delete all message_content blocks for these messages
            if message_ids and self.message_content_repo:
                try:
                    total_blocks_deleted = 0
                    for message_id in message_ids:
                        deleted_count = await self.message_content_repo.delete_blocks_by_message_id(message_id)
                        total_blocks_deleted += deleted_count
                    if total_blocks_deleted > 0:
                        logger.info(f"Deleted {total_blocks_deleted} content blocks for {len(message_ids)} messages in thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete message content blocks for thread {thread_id}: {e}")
                    # Don't fail the whole operation if content block cleanup fails
            
            # Delete the messages
            await self.messages_repo.delete_messages_by_thread(thread_id)
            
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
    
    async def get_thread_count(self, user_id: Optional[str] = None) -> int:
    
        try:
            return await self.chat_thread_repo.count_threads(user_id=user_id)
        except Exception as e:
            logger.error(f"Error counting chat threads: {e}")
            return 0
