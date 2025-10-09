from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
from bson import ObjectId
import logging

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)

class CheckpointWriteEntry:
    
    def __init__(self, checkpoint_id: str, data: Dict[str, Any], 
                 thread_id: str = None, created_at: datetime = None, updated_at: datetime = None):
        self.checkpoint_id = checkpoint_id
        self.data = data
        self.thread_id = thread_id
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "data": self.data,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class CheckpointEntry:
    
    def __init__(self, checkpoint_id: str, checkpoint_data: Dict[str, Any], 
                 thread_id: str = None, created_at: datetime = None):
        self.checkpoint_id = checkpoint_id
        self.checkpoint_data = checkpoint_data
        self.thread_id = thread_id
        self.created_at = created_at or datetime.now()
    
    def dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_data": self.checkpoint_data,
            "thread_id": self.thread_id,
            "created_at": self.created_at
        }

class CheckpointWriteRepository(BaseRepository[CheckpointWriteEntry]):
    def __init__(self, database: Database):
        super().__init__(database, "checkpointing_db.checkpoint_writes")
    
    async def _create_indexes(self) -> None:
        try:
            await self.collection.create_index("checkpoint_id")
            await self.collection.create_index("thread_id")
            await self.collection.create_index([("created_at", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create checkpoint write indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> CheckpointWriteEntry:
   
        return CheckpointWriteEntry(
            checkpoint_id=data["checkpoint_id"],
            data=data["data"],
            thread_id=data.get("thread_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )
    
    def _to_document(self, entity: CheckpointWriteEntry) -> Dict[str, Any]:
   
        return entity.dict()
    
    async def create_checkpoint_write(self, checkpoint_write: CheckpointWriteEntry) -> bool:
   
        return await self.create(checkpoint_write)
    
    async def delete_by_thread_id(self, thread_id: str) -> int:

        try:
            result = await self.collection.delete_many({"thread_id": thread_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted {result.deleted_count} checkpoint writes for thread_id: {thread_id}")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint writes for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes for thread: {e}")
    
    async def delete_by_checkpoint_id(self, checkpoint_id: str) -> int:
    
        try:
            result = await self.collection.delete_many({"checkpoint_id": checkpoint_id})
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint writes for {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes: {e}")
    
    async def delete_by_object_id(self, write_id: str) -> bool:
    
        try:
            result = await self.collection.delete_one({"_id": ObjectId(write_id)})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint write with id {write_id}: {e}")
            raise Exception(f"Failed to delete checkpoint write: {e}")
    
    async def find_by_checkpoint_id(self, checkpoint_id: str, limit: int = 100, skip: int = 0) -> List[CheckpointWriteEntry]:
    
        return await self.find_many(
            {"checkpoint_id": checkpoint_id},
            limit=limit,
            skip=skip,
            sort_criteria=[("created_at", -1)]
        )

class CheckpointRepository(BaseRepository[CheckpointEntry]):
    
    
    def __init__(self, database: Database):
        super().__init__(database, "checkpointing_db.checkpoints")
    
    async def _create_indexes(self) -> None:
        try:
            await self.collection.create_index("checkpoint_id", unique=True)
            await self.collection.create_index("thread_id")
            await self.collection.create_index([("created_at", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create checkpoint indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> CheckpointEntry:
   
        return CheckpointEntry(
            checkpoint_id=data["checkpoint_id"],
            checkpoint_data=data["checkpoint_data"],
            thread_id=data.get("thread_id"),
            created_at=data.get("created_at")
        )
    
    def _to_document(self, entity: CheckpointEntry) -> Dict[str, Any]:
   
        return entity.dict()
    
    async def create_checkpoint(self, checkpoint: CheckpointEntry) -> bool:
   
        return await self.create(checkpoint)
    
    async def delete_by_thread_id(self, thread_id: str) -> int:
   
        try:
            result = await self.collection.delete_many({"thread_id": thread_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted {result.deleted_count} checkpoints for thread_id: {thread_id}")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoints for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoints for thread: {e}")
    
    async def delete_by_checkpoint_id(self, checkpoint_id: str) -> bool:
   
        return await self.delete_by_id(checkpoint_id, "checkpoint_id")
    
    async def find_by_checkpoint_id(self, checkpoint_id: str) -> Optional[CheckpointEntry]:
   
        return await self.find_by_id(checkpoint_id, "checkpoint_id")
    
    async def get_all_checkpoints(self, limit: int = 100, skip: int = 0) -> List[CheckpointEntry]:
   
        return await self.find_many(
            limit=limit,
            skip=skip,
            sort_criteria=[("created_at", -1)]
        )
