import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError

from .base_repository import BaseRepository
from src.models.chat_models import ChatMessage

logger = logging.getLogger(__name__)

class MessagesRepository(BaseRepository[ChatMessage]):
    
    def __init__(self, database: Database):
        super().__init__(database, "messages")
    
    async def _create_indexes(self) -> None:
        try:
            # Core indexes for message identification and retrieval
            await self.collection.create_index("message_id", unique=True, name="idx_message_id_unique")
            await self.collection.create_index("thread_id", name="idx_thread_id")
            
            # Compound indexes for efficient thread-based queries
            await self.collection.create_index([("thread_id", 1), ("timestamp", 1)], name="idx_thread_timestamp_asc")
            await self.collection.create_index([("thread_id", 1), ("timestamp", -1)], name="idx_thread_timestamp_desc")
            await self.collection.create_index([("thread_id", 1), ("sender", 1), ("timestamp", -1)], name="idx_thread_sender_timestamp")
            
            # Status-based filtering indexes for message management
            await self.collection.create_index([("thread_id", 1), ("message_status", 1)], name="idx_thread_status")
            await self.collection.create_index([("thread_id", 1), ("message_type", 1)], name="idx_thread_message_type")
            
            # Performance indexes for common queries
            await self.collection.create_index([("sender", 1), ("timestamp", -1)], name="idx_sender_timestamp")
            await self.collection.create_index([("message_type", 1), ("timestamp", -1)], name="idx_message_type_timestamp")
            await self.collection.create_index([("checkpoint_id", 1)], sparse=True, name="idx_checkpoint_id")
            # User-based queries for execution history
            await self.collection.create_index([("user_id", 1), ("checkpoint_id", 1)], sparse=True, name="idx_user_checkpoint")
            await self.collection.create_index([("user_id", 1), ("timestamp", -1)], name="idx_user_timestamp")
            
            # Audit and maintenance indexes
            await self.collection.create_index([("updated_at", -1)], name="idx_updated_at")
            await self.collection.create_index([("created_at", -1)], name="idx_created_at")
            
            # Text search index for message content (optional, for future search features)
            # await self.collection.create_index([("content", "text")], name="idx_content_text")
            
            logger.info("Successfully created optimized message indexes")
        except PyMongoError as e:
            logger.warning(f"Could not create messages indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> ChatMessage:
        return ChatMessage(**data)
    
    def _to_document(self, entity: ChatMessage) -> Dict[str, Any]:
        return entity.dict()
    
    async def add_message(self, message: ChatMessage) -> bool:
        return await self.create(message)
    
    async def update_message_by_message_id(self, message_id: int, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a message using its message_id."""
        # Remove None values to avoid overwriting fields with null unintentionally
        safe_updates = {k: v for k, v in updates.items() if v is not None}
        return await self.update_by_id(message_id, safe_updates, id_field="message_id")

    async def get_message_by_id(self, thread_id: str, message_id: int) -> Optional[ChatMessage]:
        """Get a specific message by its ID within a thread."""
        try:
            document = await self.collection.find_one({
                "thread_id": thread_id,
                "message_id": message_id
            })
            if document:
                document.pop('_id', None)
                return self._to_entity(document)
            return None
        except PyMongoError as e:
            logger.error(f"Error finding message {message_id} in thread {thread_id}: {e}")
            raise Exception(f"Failed to find message: {e}")

    async def delete_message(self, message: ChatMessage) -> bool:
        return await self.delete_by_id(message.message_id, "message_id")
    
    async def get_last_message_by_thread(self, thread_id: str) -> Optional[ChatMessage]:
        try:
            document = await self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]  # Sort by timestamp descending
            )
            if document:
                document.pop('_id', None)
                return self._to_entity(document)
            return None
        except PyMongoError as e:
            logger.error(f"Error finding last message for thread {thread_id}: {e}")
            raise Exception(f"Failed to find last message: {e}")

    async def get_all_messages_by_thread(self, thread_id: str, 
                                       limit: Optional[int] = None, 
                                       skip: Optional[int] = None) -> List[ChatMessage]:
        """Get all messages from a specific thread, ordered by timestamp"""
        try:
            filter_criteria = {"thread_id": thread_id}
            sort_criteria = [("timestamp", 1)]  # Sort chronologically
            
            return await self.find_many(
                filter_criteria=filter_criteria,
                limit=limit,
                skip=skip,
                sort_criteria=sort_criteria
            )
        except PyMongoError as e:
            logger.error(f"Error finding messages for thread {thread_id}: {e}")
            raise Exception(f"Failed to find messages for thread: {e}")

    async def get_messages_by_thread_paginated(self, thread_id: str, 
                                             page: int = 1, 
                                             page_size: int = 50) -> Dict[str, Any]:
        """Get paginated messages from a thread with metadata"""
        try:
            skip = (page - 1) * page_size
            
            # Get messages and total count in parallel
            messages_task = self.get_all_messages_by_thread(
                thread_id=thread_id, 
                limit=page_size, 
                skip=skip
            )
            count_task = self.count_messages_by_thread(thread_id)
            
            messages, total_count = await asyncio.gather(messages_task, count_task)
            
            return {
                "messages": messages,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_messages": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": page * page_size < total_count,
                    "has_previous": page > 1
                }
            }
        except PyMongoError as e:
            logger.error(f"Error getting paginated messages for thread {thread_id}: {e}")
            raise Exception(f"Failed to get paginated messages: {e}")

    async def count_messages_by_thread(self, thread_id: str) -> int:
        return await self.collection.count_documents({"thread_id": thread_id})
    
    async def delete_messages_by_thread(self, thread_id: str) -> bool:
        """Delete all messages for a specific thread"""
        try:
            deleted_count = await self.delete_many({"thread_id": thread_id})
            logger.info(f"Deleted {deleted_count} messages for thread {thread_id}")
            return deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting messages for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete messages: {e}")

    async def get_checkpoints_by_user_id(self, user_id: str, limit: Optional[int] = None, skip: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get distinct checkpoints for a user across all threads, sorted by timestamp descending"""
        try:
            # Pipeline to get distinct checkpoints with metadata
            pipeline = [
                # Match messages with checkpoint_id and user_id
                {
                    "$match": {
                        "user_id": user_id,
                        "checkpoint_id": {"$exists": True, "$ne": None}
                    }
                },
                # Sort by timestamp descending
                {"$sort": {"timestamp": -1}},
                # Group by checkpoint_id to get unique checkpoints
                {
                    "$group": {
                        "_id": "$checkpoint_id",
                        "checkpoint_id": {"$first": "$checkpoint_id"},
                        "thread_id": {"$first": "$thread_id"},
                        "timestamp": {"$first": "$timestamp"},
                        "message_type": {"$first": "$message_type"},
                        "message_id": {"$first": "$message_id"}
                    }
                },
                # Sort grouped results by timestamp descending
                {"$sort": {"timestamp": -1}},
                # Project final fields
                {
                    "$project": {
                        "_id": 0,
                        "checkpoint_id": 1,
                        "thread_id": 1,
                        "timestamp": 1,
                        "message_type": 1,
                        "message_id": 1
                    }
                }
            ]
            
            # Add skip and limit if provided
            if skip:
                pipeline.append({"$skip": skip})
            if limit:
                pipeline.append({"$limit": limit})
            
          
            results = []
            cursor = await self.collection.aggregate(pipeline)
            async for doc in cursor:
                results.append(doc)
            
            return results
        except PyMongoError as e:
            logger.error(f"Error finding checkpoints for user {user_id}: {e}")
            raise Exception(f"Failed to find checkpoints: {e}")

    async def count_checkpoints_by_user_id(self, user_id: str) -> int:
        """Count distinct checkpoints for a user"""
        try:
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "checkpoint_id": {"$exists": True, "$ne": None}
                    }
                },
                {
                    "$group": {
                        "_id": "$checkpoint_id"
                    }
                },
                {
                    "$count": "total"
                }
            ]
            
            # For Motor: iterate the cursor directly
            cursor = await self.collection.aggregate(pipeline)
            result = None
            async for doc in cursor:
                result = doc
                break
            
            if result and "total" in result:
                return result.get("total", 0)
            return 0
        except PyMongoError as e:
            logger.error(f"Error counting checkpoints for user {user_id}: {e}")
            raise Exception(f"Failed to count checkpoints: {e}")