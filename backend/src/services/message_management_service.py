import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from src.repositories.messages_repository import MessagesRepository
from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.message_content_repository import MessageContentRepository
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
                 chat_thread_repo: ChatThreadRepository,
                 message_content_repo: MessageContentRepository):
        self.messages_repo = messages_repo
        self.chat_thread_repo = chat_thread_repo
        self.message_content_repo = message_content_repo
    
    async def save_user_message(self, 
                               thread_id: str,
                               content: Optional[Any] = None,  # Can be string or List[Dict]
                               message_id: Optional[int] = None,
                               message_type: Literal["message", "explorer", "visualization", "structured"] = "message",
                               content_blocks: Optional[List[Dict[str, Any]]] = None,
                               metadata: Optional[dict] = None,
                               user_id: Optional[str] = None,
                               is_feedback: bool = False) -> ChatMessage:
        """
        Save a user message with proper validation and security checks.
        This is called when the backend receives a user message.
        Content can be passed as array of blocks, or content_blocks parameter (for backward compatibility).
        """
        try:
            thread = await self.chat_thread_repo.find_by_id(thread_id, "thread_id")
            
            if not thread:
                raise ValueError(f"Thread {thread_id} not found")
            
            # Get user_id from thread if not provided
            if user_id is None:
                user_id = getattr(thread, 'user_id', None)
            
            # Generate message ID if not provided
            if message_id is None:
                message_id = int(time.time() * 1000000)  # Microsecond precision
                logger.info(f"Generated message_id: {message_id} for thread {thread_id}")
            
            # Normalize content: use content_blocks if provided (backward compat), otherwise use content
            # If content is a string, convert it to a text block
            if content_blocks is not None:
                blocks = content_blocks
            elif content is not None:
                if isinstance(content, str) and content.strip():
                    # Convert string content to a text block
                    blocks = [{
                        "id": f"text_{message_id or int(time.time() * 1000)}",
                        "type": "text",
                        "needsApproval": False,
                        "data": {"text": content}
                    }]
                elif isinstance(content, list):
                    blocks = content
                else:
                    blocks = []
            else:
                blocks = []
            
            # If blocks exist, determine message type
            if blocks and message_type == "message":
                message_type = "structured"
            
            # Create message object with empty content array (blocks stored separately)
            message = ChatMessage(
                thread_id=thread_id,
                sender="user",
                content=[],  # Always empty - blocks stored in message_content collection
                timestamp=datetime.now(),
                message_type=message_type,
                message_id=message_id,
                user_id=user_id,
                message_status=None,
                checkpoint_id=None
            )
            
            if user_id:
                logger.info(f"Saving user message {message_id} to thread {thread_id} with user_id: {user_id}")
            
            # Save message to database
            success = await self.messages_repo.add_message(message)
            if not success:
                raise RuntimeError("Failed to save user message to database")
            
            # Save content blocks to message_content collection
            if blocks:
                await self.message_content_repo.add_content_blocks(message_id, blocks)
                # Load blocks back into message for return value
                message.content = await self.message_content_repo.get_blocks_by_message_id(message_id)
            
            logger.info(f"Successfully saved user message {message_id} to thread {thread_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error saving user message to thread {thread_id}: {e}")
            raise
    
    async def save_assistant_message(self,
                                   thread_id: str,
                                   content: Optional[Any] = None,  # Can be string or List[Dict]
                                   message_type: Literal["message", "explorer", "visualization", "structured"] = "message",
                                   checkpoint_id: Optional[str] = None,
                                   needs_approval: bool = False,
                                   content_blocks: Optional[List[Dict[str, Any]]] = None,
                                   metadata: Optional[dict] = None,
                                   message_id: Optional[int] = None,
                                   user_id: Optional[str] = None) -> ChatMessage:
        """
        Save an assistant message. This is called by the backend during graph execution.
        Only the backend should create assistant messages for security.
        Content can be passed as array of blocks, or content_blocks parameter (for backward compatibility).
        """
        try:
            # For assistant messages, we trust the backend - thread should exist since 
            # assistant messages are only created during active graph execution
            
            # Get user_id from thread if not provided
            if user_id is None:
                try:
                    thread = await self.chat_thread_repo.find_by_id(thread_id, "thread_id")
                    if thread:
                        user_id = getattr(thread, 'user_id', None)
                except Exception:
                    pass  # Thread might not exist yet, user_id will be None
            
            # Generate unique message ID only if not provided
            if message_id is None:
                message_id = int(time.time() * 1000000)
            
            # Normalize content: use content_blocks if provided (backward compat), otherwise use content
            # If content is a string, convert it to a text block
            if content_blocks is not None:
                blocks = content_blocks
            elif content is not None:
                if isinstance(content, str) and content.strip():
                    # Convert string content to a text block
                    blocks = [{
                        "id": f"text_{message_id or int(time.time() * 1000)}",
                        "type": "text",
                        "needsApproval": False,
                        "data": {"text": content}
                    }]
                elif isinstance(content, list):
                    blocks = content
                else:
                    blocks = []
            else:
                blocks = []
            
            # Determine message type based on content blocks
            if blocks and message_type == "message":
                message_type = "structured"
            
            # Create message object with empty content array (blocks stored separately)
            message = ChatMessage(
                thread_id=thread_id,
                sender="assistant",
                content=[],  # Always empty - blocks stored in message_content collection
                timestamp=datetime.now(),
                message_type=message_type,
                message_id=message_id,
                user_id=user_id,
                checkpoint_id=checkpoint_id,
                # Only set status if needs_approval, otherwise leave as None
                message_status="pending" if needs_approval else None,
                metadata=metadata
            )
            
            if user_id:
                logger.info(f"Saving assistant message {message_id} to thread {thread_id} with user_id: {user_id}")
            
            # Save message to database
            success = await self.messages_repo.add_message(message)
            if not success:
                raise RuntimeError("Failed to save assistant message to database")
            
            # Save content blocks to message_content collection
            if blocks:
                await self.message_content_repo.add_content_blocks(message_id, blocks)
                # Load blocks back into message for return value
                message.content = await self.message_content_repo.get_blocks_by_message_id(message_id)
            
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
            
            # Filter valid status fields - only message_status is supported now
            valid_fields = {
                'message_status'
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
        Mark a message as having an error and optionally add error block.
        """
        try:
            # Update message status to error
            updates = {
                'message_status': 'error'
            }
            
            # If error message provided, add error block to content
            if error_message:
                # Get current message to preserve original content
                message = await self._get_message_by_id(thread_id, message_id)
                if message:
                    error_block = {
                        "id": f"error_{message_id}_{int(time.time() * 1000)}",
                        "type": "text",
                        "needsApproval": False,
                        "data": {"text": f"Error: {error_message}"}
                    }
                    await self.message_content_repo.add_content_blocks(message_id, [error_block])
            
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
        Content blocks are loaded from message_content collection.
        """
        try:
            # Use optimized repository method with filtering
            if sender_filter or message_type_filter or status_filter:
                messages = await self._get_filtered_messages(
                    thread_id, limit, skip, sender_filter, message_type_filter, status_filter
                )
            else:
                messages = await self.messages_repo.get_all_messages_by_thread(
                    thread_id, limit=limit, skip=skip
                )
            
            # Load content blocks for each message
            for message in messages:
                message.content = await self.message_content_repo.get_blocks_by_message_id(message.message_id)
            
            return messages
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
        Content blocks are loaded separately.
        """
        # Build filter criteria for optimized database query
        filter_criteria = {"thread_id": thread_id}
        
        if sender_filter:
            filter_criteria["sender"] = sender_filter
        
        if message_type_filter:
            filter_criteria["message_type"] = message_type_filter
        
        if status_filter:
            for status_key, status_value in status_filter.items():
                if status_key in ['message_status']:
                    filter_criteria[status_key] = status_value
        
        # Use repository's find_many method with optimized filters
        messages = await self.messages_repo.find_many(
            filter_criteria=filter_criteria,
            limit=limit,
            skip=skip,
            sort_criteria=[("timestamp", 1)]  # Chronological order
        )
        
        # Load content blocks for each message
        for message in messages:
            message.content = await self.message_content_repo.get_blocks_by_message_id(message.message_id)
        
        return messages
    
    async def get_last_message(self, thread_id: str) -> Optional[ChatMessage]:
        """
        Get the last message in a thread.
        Content blocks are loaded from message_content collection.
        """
        try:
            message = await self.messages_repo.get_last_message_by_thread(thread_id)
            if message:
                message.content = await self.message_content_repo.get_blocks_by_message_id(message.message_id)
            return message
        except Exception as e:
            logger.error(f"Error retrieving last message for thread {thread_id}: {e}")
            return None
    
    def _sanitize_content(self, content: Any) -> Any:
        """
        Sanitize message content for security and consistency.
        Handles both string content (legacy) and list of blocks.
        """
        if isinstance(content, str):
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
        Content blocks are loaded from message_content collection.
        """
        try:
            message = await self.messages_repo.get_message_by_id(thread_id, message_id)
            if message:
                message.content = await self.message_content_repo.get_blocks_by_message_id(message_id)
            return message
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
    
    async def update_block_status(self,
                                  thread_id: str,
                                  message_id: int,
                                  block_id: str,
                                  **status_updates) -> bool:
        """
        Update block-level approval status in message_content collection.
        Only backend should control these for security.
        """
        try:
            # Validate the message exists and belongs to the thread
            message = await self.messages_repo.get_message_by_id(thread_id, message_id)
            if not message:
                raise ValueError(f"Message {message_id} not found in thread {thread_id}")
            
            # Filter valid status fields for blocks
            valid_fields = {
                'needsApproval', 'messageStatus', 'message_status'
            }
            
            filtered_updates = {k: v for k, v in status_updates.items() if k in valid_fields}
            
            if not filtered_updates:
                logger.warning(f"No valid block status updates provided for block {block_id} in message {message_id}")
                return False
            
            # Update the block in message_content collection
            success = await self.message_content_repo.update_block(block_id, filtered_updates)
            
            if success:
                logger.info(f"Updated block {block_id} status in message {message_id}: {filtered_updates}")
            else:
                logger.error(f"Failed to update block {block_id} status in message {message_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating block {block_id} status in message {message_id}: {e}")
            raise