import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from src.repositories.messages_repository import MessagesRepository
from src.repositories.chat_thread_repository import ChatThreadRepository
from src.models.chat_models import ChatMessage, AddMessageRequest
# Retry and circuit breaker utilities removed for simpler development

logger = logging.getLogger(__name__)

class MessageManagementService:
    """
    Centralized service for managing chat messages with proper validation,
    security, and production-ready features.
    """
    
    def __init__(self, 
                 messages_repo: MessagesRepository,
                 chat_thread_repo: ChatThreadRepository):
        self.messages_repo = messages_repo
        self.chat_thread_repo = chat_thread_repo
    
    async def save_user_message(self, 
                               thread_id: str,
                               content: str,
                               message_id: Optional[int] = None,
                               message_type: Literal["message", "explorer", "visualization"] = "message",
                               metadata: Optional[dict] = None) -> ChatMessage:
        """
        Save a user message with proper validation and security checks.
        This is called when the backend receives a user message.
        """
        try:
      
            thread = await self.chat_thread_repo.find_by_id(thread_id, "thread_id")

            
            if not thread:
                raise ValueError(f"Thread {thread_id} not found")
            
            # Generate message ID if not provided
            if message_id is None:
                message_id = int(time.time() * 1000000)  # Microsecond precision
                logger.info(f"Generated message_id: {message_id} for thread {thread_id}")
            
            # Sanitize and validate content
            content = self._sanitize_content(content)
            if not content.strip():
                raise ValueError("Message content cannot be empty")
            
            # Create message object
            message = ChatMessage(
                thread_id=thread_id,
                sender="user",
                content=content,
                timestamp=datetime.now(),
                message_type=message_type,
                message_id=message_id,
                # User messages don't need approval by default
                needs_approval=False,
                approved=None,
                disapproved=None,
                is_error=False,
                is_feedback=False,
                has_timed_out=False,
                can_retry=False,
                retry_action=None,
                checkpoint_id=None
            )
            
            # Save to database
            success = await self.messages_repo.add_message(message)
            if not success:
                raise RuntimeError("Failed to save user message to database")
            
            logger.info(f"Successfully saved user message {message_id} to thread {thread_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error saving user message to thread {thread_id}: {e}")
            raise
    
    async def save_assistant_message(self,
                                   thread_id: str,
                                   content: str,
                                   message_type: Literal["message", "explorer", "visualization"] = "message",
                                   checkpoint_id: Optional[str] = None,
                                   needs_approval: bool = False,
                                   metadata: Optional[dict] = None,
                                   message_id: Optional[int] = None) -> ChatMessage:
        """
        Save an assistant message. This is called by the backend during graph execution.
        Only the backend should create assistant messages for security.
        """
        try:
            # For assistant messages, we trust the backend - thread should exist since 
            # assistant messages are only created during active graph execution
            
            # Generate unique message ID only if not provided
            if message_id is None:
                message_id = int(time.time() * 1000000)
            
            # Sanitize content
            content = self._sanitize_content(content)
            
            # Create message object
            message = ChatMessage(
                thread_id=thread_id,
                sender="assistant",
                content=content,
                timestamp=datetime.now(),
                message_type=message_type,
                message_id=message_id,
                checkpoint_id=checkpoint_id,
                needs_approval=needs_approval,
                approved=None,
                disapproved=None,
                is_error=False,
                is_feedback=False,
                has_timed_out=False,
                can_retry=True if needs_approval else False,
                retry_action="approve" if needs_approval else None,
                metadata=metadata
            )
            
            # Save to database
            success = await self.messages_repo.add_message(message)
            if not success:
                raise RuntimeError("Failed to save assistant message to database")
            
            logger.info(f"Successfully saved assistant message {message_id} to thread {thread_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error saving assistant message to thread {thread_id}: {e}")
            raise
    
    async def update_message_status(self,
                                  thread_id: str,
                                  message_id: int,
                                  **status_updates) -> bool:
        """
        Update message status flags. Only backend should control these for security.
        """
        try:
            # Validate the message exists and belongs to the thread
            message = await self._get_message_by_id(thread_id, message_id)
            if not message:
                raise ValueError(f"Message {message_id} not found in thread {thread_id}")
            
            # Filter valid status fields
            valid_fields = {
                'needs_approval', 'approved', 'disapproved', 'is_error', 
                'is_feedback', 'has_timed_out', 'can_retry', 'retry_action'
            }
            
            filtered_updates = {k: v for k, v in status_updates.items() if k in valid_fields}
            
            if not filtered_updates:
                logger.warning(f"No valid status updates provided for message {message_id}")
                return False
            
            # Update in database
            success = await self.messages_repo.update_message_by_message_id(
                message_id, filtered_updates
            )
            
            if success:
                logger.info(f"Updated message {message_id} status: {filtered_updates}")
            else:
                logger.error(f"Failed to update message {message_id} status")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating message {message_id} status: {e}")
            raise
    
    async def mark_message_error(self,
                               thread_id: str,
                               message_id: int,
                               error_message: str = None) -> bool:
        """
        Mark a message as having an error and optionally update content.
        """
        try:
            updates = {
                'is_error': True,
                'can_retry': True,
                'retry_action': 'cancel'
            }
            
            # If error message provided, update content
            if error_message:
                # Get current message to preserve original content
                message = await self._get_message_by_id(thread_id, message_id)
                if message:
                    error_content = f"Error: {error_message}\n\nOriginal: {message.content}"
                    await self.messages_repo.update_message_by_message_id(
                        message_id, {'content': error_content}
                    )
            
            return await self.update_message_status(thread_id, message_id, **updates)
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as error: {e}")
            return False
    
    async def get_thread_messages(self, 
                                thread_id: str,
                                limit: Optional[int] = None,
                                skip: Optional[int] = None,
                                sender_filter: Optional[str] = None,
                                message_type_filter: Optional[str] = None,
                                status_filter: Optional[Dict[str, bool]] = None) -> List[ChatMessage]:
        """
        Get messages for a thread with optional pagination and filtering.
        Enhanced with performance optimizations and filtering capabilities.
        """
        try:
            # Use optimized repository method with filtering
            if sender_filter or message_type_filter or status_filter:
                return await self._get_filtered_messages(
                    thread_id, limit, skip, sender_filter, message_type_filter, status_filter
                )
            
            return await self.messages_repo.get_all_messages_by_thread(
                thread_id, limit=limit, skip=skip
            )
        except Exception as e:
            logger.error(f"Error retrieving messages for thread {thread_id}: {e}")
            raise
    
    async def _get_filtered_messages(self,
                                   thread_id: str,
                                   limit: Optional[int],
                                   skip: Optional[int],
                                   sender_filter: Optional[str],
                                   message_type_filter: Optional[str],
                                   status_filter: Optional[Dict[str, bool]]) -> List[ChatMessage]:
        """
        Internal method for filtered message retrieval with optimized queries.
        """
        # Build filter criteria for optimized database query
        filter_criteria = {"thread_id": thread_id}
        
        if sender_filter:
            filter_criteria["sender"] = sender_filter
        
        if message_type_filter:
            filter_criteria["message_type"] = message_type_filter
        
        if status_filter:
            for status_key, status_value in status_filter.items():
                if status_key in ['needs_approval', 'approved', 'disapproved', 'is_error', 'is_feedback']:
                    filter_criteria[status_key] = status_value
        
        # Use repository's find_many method with optimized filters
        return await self.messages_repo.find_many(
            filter_criteria=filter_criteria,
            limit=limit,
            skip=skip,
            sort_criteria=[("timestamp", 1)]  # Chronological order
        )
    
    async def get_last_message(self, thread_id: str) -> Optional[ChatMessage]:
        """
        Get the last message in a thread.
        """
        try:
            return await self.messages_repo.get_last_message_by_thread(thread_id)
        except Exception as e:
            logger.error(f"Error retrieving last message for thread {thread_id}: {e}")
            return None
    
    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize message content for security and consistency.
        """
        if not isinstance(content, str):
            content = str(content)
        
        # Basic sanitization - remove null bytes and excessive whitespace
        content = content.replace('\x00', '').strip()
        
        # Limit content length for security (10MB limit)
        max_length = 10 * 1024 * 1024  # 10MB
        if len(content) > max_length:
            content = content[:max_length] + "... [truncated]"
            logger.warning(f"Message content truncated to {max_length} characters")
        
        return content
    
    async def _get_message_by_id(self, thread_id: str, message_id: int) -> Optional[ChatMessage]:
        """
        Helper to get a specific message by ID within a thread.
        """
        try:
            messages = await self.messages_repo.get_all_messages_by_thread(thread_id)
            for message in messages:
                if message.message_id == message_id:
                    return message
            return None
        except Exception as e:
            logger.error(f"Error finding message {message_id} in thread {thread_id}: {e}")
            return None
    
    async def validate_message_ownership(self, thread_id: str, message_id: int, expected_sender: str) -> bool:
        """
        Validate that a message belongs to the expected sender for security.
        """
        try:
            message = await self._get_message_by_id(thread_id, message_id)
            if not message:
                return False
            return message.sender == expected_sender
        except Exception as e:
            logger.error(f"Error validating message ownership: {e}")
            return False
