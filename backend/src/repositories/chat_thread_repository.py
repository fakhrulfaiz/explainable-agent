from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
import logging

from .base_repository import BaseRepository
from src.models.chat_models import ChatThread, ChatMessage, ChatThreadSummary

logger = logging.getLogger(__name__)

class ChatThreadRepository(BaseRepository[ChatThread]):
    
    def __init__(self, database: Database):
        super().__init__(database, "chat_threads")
    
    def _create_indexes(self) -> None:
   
        try:
            # Index on thread_id for fast lookups
            self.collection.create_index("thread_id", unique=True)
            # Index on updated_at for sorting by recency
            self.collection.create_index([("updated_at", -1)])
            # Index on created_at for sorting by creation time
            self.collection.create_index([("created_at", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create chat thread indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> ChatThread:
        return ChatThread(**data)
    
    def _to_document(self, entity: ChatThread) -> Dict[str, Any]:
        return entity.dict()
    
    async def find_by_thread_id(self, thread_id: str) -> Optional[ChatThread]:
        return await self.find_by_id(thread_id, "thread_id")
    
    async def create_thread(self, thread: ChatThread) -> bool:
        return await self.create(thread)
     
    async def update_thread_title(self, thread_id: str, title: str) -> bool:
        return await self.update_by_id(
            thread_id, 
            {"title": title, "updated_at": datetime.now()}, 
            "thread_id"
        )
    
    async def delete_thread(self, thread_id: str) -> bool:
        return await self.delete_by_id(thread_id, "thread_id")
    
    async def get_threads(self, limit: int = 50, skip: int = 0) -> List[ChatThread]:
    
        try:
            cursor = self.collection.find(
                {},
                {
                    "thread_id": 1,
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1,
                }
            ).sort("updated_at", -1).skip(skip).limit(limit)
            
            summaries = []
            async for thread_data in cursor:
               
                summary = ChatThread(
                    thread_id=thread_data["thread_id"],
                    title=thread_data.get("title", "Untitled Chat"),
                    created_at=thread_data["created_at"],
                    updated_at=thread_data["updated_at"]
                )
                summaries.append(summary)
            
            return summaries
            
        except PyMongoError as e:
            logger.error(f"Error retrieving chat thread summaries: {e}")
            raise Exception(f"Failed to retrieve chat thread summaries: {e}")
    
    async def count_threads(self) -> int:
        return await self.count()
