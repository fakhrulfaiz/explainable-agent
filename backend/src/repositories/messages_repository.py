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
            # Create unique index on message_id - all messages must have a unique message_id
            await self.collection.create_index("message_id", unique=True)
            await self.collection.create_index("thread_id")
            await self.collection.create_index([("thread_id", 1), ("timestamp", 1)])
            await self.collection.create_index([("thread_id", 1), ("timestamp", -1)])
            await self.collection.create_index([("updated_at", -1)])
            await self.collection.create_index([("created_at", -1)])
            await self.collection.create_index([("sender", 1), ("timestamp", -1)])
            await self.collection.create_index("message_type")
        except PyMongoError as e:
            logger.warning(f"Could not create messages indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> ChatMessage:
        return ChatMessage(**data)
    
    def _to_document(self, entity: ChatMessage) -> Dict[str, Any]:
        return entity.dict()
    
    async def add_message(self, message: ChatMessage) -> bool:
        return await self.create(message)
    
    async def delete_message(self, message: ChatMessage) -> bool:
        return await self.delete_by_id(message.message_id, "message_id")
    
    async def get_last_message_by_thread(self, thread_id: str) -> Optional[ChatMessage]:
        try:
            print(f"Searching for messages with thread_id: {thread_id}")
            document = await self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]  # Sort by timestamp descending
            )
            print(f"Found document: {document}")
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