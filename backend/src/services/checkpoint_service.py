from typing import Dict, Any, Optional, List
from datetime import datetime
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from src.models.database import get_mongodb
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service for managing MongoDB checkpoint operations"""
    
    def __init__(self, database: Database):
        self.db = database
    
        self.checkpoint_writes_collection: Collection = self.db["checkpointing_db.checkpoint_writes"]
        self.checkpoints_collection: Collection = self.db["checkpointing_db.checkpoints"]
        # Create indexes for better performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for efficient querying"""
        try:
            # Index on checkpoint_id for fast lookups in both collections
            self.checkpoint_writes_collection.create_index("checkpoint_id")
            self.checkpoints_collection.create_index("checkpoint_id", unique=True)
            # Index on thread_id for fast deletion when threads are removed
            self.checkpoint_writes_collection.create_index("thread_id")
            self.checkpoints_collection.create_index("thread_id")
            # Index on created_at for sorting by creation time
            self.checkpoint_writes_collection.create_index([("created_at", -1)])
            self.checkpoints_collection.create_index([("created_at", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create checkpoint indexes: {e}")
    
    # Checkpoint Writes Operations
    async def add_checkpoint_write(self, checkpoint_id: str, data: Dict[str, Any]) -> bool:
        """Add a new checkpoint write entry"""
        try:
            write_entry = {
                "checkpoint_id": checkpoint_id,
                "data": data,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            result = self.checkpoint_writes_collection.insert_one(write_entry)
            
            if result.inserted_id:
                logger.info(f"Added checkpoint write for checkpoint_id: {checkpoint_id}")
                return True
            else:
                logger.warning(f"Failed to add checkpoint write for checkpoint_id: {checkpoint_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error adding checkpoint write for {checkpoint_id}: {e}")
            raise Exception(f"Failed to add checkpoint write: {e}")
    
    async def delete_checkpoint_writes_by_thread(self, thread_id: str) -> int:
        """Delete all checkpoint writes for a specific thread_id"""
        try:
            result = self.checkpoint_writes_collection.delete_many({"thread_id": thread_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted {result.deleted_count} checkpoint writes for thread_id: {thread_id}")
            
            return result.deleted_count
                
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint writes for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes for thread: {e}")
    
    async def delete_checkpoint_write(self, checkpoint_id: str) -> bool:
        """Delete checkpoint write entries by checkpoint_id"""
        try:
            result = self.checkpoint_writes_collection.delete_many({"checkpoint_id": checkpoint_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted {result.deleted_count} checkpoint write(s) for checkpoint_id: {checkpoint_id}")
                return True
            else:
                logger.warning(f"No checkpoint writes found for checkpoint_id: {checkpoint_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint writes for {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes: {e}")
    
    async def delete_checkpoint_write_by_id(self, write_id: str) -> bool:
        """Delete a specific checkpoint write entry by its MongoDB ObjectId"""
        try:
            from bson import ObjectId
            result = self.checkpoint_writes_collection.delete_one({"_id": ObjectId(write_id)})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted checkpoint write with id: {write_id}")
                return True
            else:
                logger.warning(f"Checkpoint write not found with id: {write_id}")
                return False
                
        except (PyMongoError, Exception) as e:
            logger.error(f"Error deleting checkpoint write {write_id}: {e}")
            raise Exception(f"Failed to delete checkpoint write: {e}")
    
    async def get_checkpoint_writes(self, checkpoint_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoint write entries for a specific checkpoint_id"""
        try:
            cursor = self.checkpoint_writes_collection.find(
                {"checkpoint_id": checkpoint_id}
            ).sort("created_at", -1)
            
            writes = []
            for write_data in cursor:
                # Convert ObjectId to string for JSON serialization
                write_data["_id"] = str(write_data["_id"])
                writes.append(write_data)
            
            logger.info(f"Retrieved {len(writes)} checkpoint writes for checkpoint_id: {checkpoint_id}")
            return writes
            
        except PyMongoError as e:
            logger.error(f"Error retrieving checkpoint writes for {checkpoint_id}: {e}")
            raise Exception(f"Failed to retrieve checkpoint writes: {e}")
    
    # Checkpoints Operations
    async def add_checkpoint(self, checkpoint_id: str, checkpoint_data: Dict[str, Any]) -> bool:
        """Add a new checkpoint entry"""
        try:
            checkpoint_entry = {
                "checkpoint_id": checkpoint_id,
                "checkpoint_data": checkpoint_data,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            result = self.checkpoints_collection.insert_one(checkpoint_entry)
            
            if result.inserted_id:
                logger.info(f"Added checkpoint: {checkpoint_id}")
                return True
            else:
                logger.warning(f"Failed to add checkpoint: {checkpoint_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error adding checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to add checkpoint: {e}")
    
    async def delete_checkpoints_by_thread(self, thread_id: str) -> int:
        """Delete all checkpoints for a specific thread_id"""
        try:
            result = self.checkpoints_collection.delete_many({"thread_id": thread_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted {result.deleted_count} checkpoints for thread_id: {thread_id}")
            
            return result.deleted_count
                
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoints for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoints for thread: {e}")
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by checkpoint_id"""
        try:
            result = self.checkpoints_collection.delete_one({"checkpoint_id": checkpoint_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted checkpoint: {checkpoint_id}")
                return True
            else:
                logger.warning(f"Checkpoint not found: {checkpoint_id}")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error deleting checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete checkpoint: {e}")
    
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific checkpoint by checkpoint_id"""
        try:
            checkpoint_data = self.checkpoints_collection.find_one({"checkpoint_id": checkpoint_id})
            
            if checkpoint_data:
                # Convert ObjectId to string for JSON serialization
                checkpoint_data["_id"] = str(checkpoint_data["_id"])
                logger.info(f"Retrieved checkpoint: {checkpoint_id}")
                return checkpoint_data
            else:
                logger.info(f"Checkpoint not found: {checkpoint_id}")
                return None
                
        except PyMongoError as e:
            logger.error(f"Error retrieving checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to retrieve checkpoint: {e}")
    
    async def get_all_checkpoints(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get all checkpoints with pagination"""
        try:
            cursor = self.checkpoints_collection.find().sort("created_at", -1).skip(skip).limit(limit)
            
            checkpoints = []
            for checkpoint_data in cursor:
                # Convert ObjectId to string for JSON serialization
                checkpoint_data["_id"] = str(checkpoint_data["_id"])
                checkpoints.append(checkpoint_data)
            
            logger.info(f"Retrieved {len(checkpoints)} checkpoints")
            return checkpoints
            
        except PyMongoError as e:
            logger.error(f"Error retrieving checkpoints: {e}")
            raise Exception(f"Failed to retrieve checkpoints: {e}")
    
    # Utility Operations
    async def delete_all_checkpoint_data(self, checkpoint_id: str) -> Dict[str, bool]:
        """Delete both checkpoint and all associated checkpoint writes"""
        try:
            # Delete from both collections
            writes_deleted = await self.delete_checkpoint_write(checkpoint_id)
            checkpoint_deleted = await self.delete_checkpoint(checkpoint_id)
            
            result = {
                "checkpoint_writes_deleted": writes_deleted,
                "checkpoint_deleted": checkpoint_deleted
            }
            
            logger.info(f"Deleted all data for checkpoint_id {checkpoint_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error deleting all checkpoint data for {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete all checkpoint data: {e}")
    
    async def delete_all_thread_data(self, thread_id: str) -> Dict[str, int]:
        """Delete all checkpoint data (writes and checkpoints) for a specific thread_id"""
        try:
            # Delete from both collections by thread_id
            writes_deleted = await self.delete_checkpoint_writes_by_thread(thread_id)
            checkpoints_deleted = await self.delete_checkpoints_by_thread(thread_id)
            
            result = {
                "checkpoint_writes_deleted": writes_deleted,
                "checkpoints_deleted": checkpoints_deleted,
                "total_deleted": writes_deleted + checkpoints_deleted
            }
            
            logger.info(f"Deleted all checkpoint data for thread_id {thread_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error deleting all thread checkpoint data for {thread_id}: {e}")
            raise Exception(f"Failed to delete thread checkpoint data: {e}")
    
    async def get_checkpoint_count(self) -> int:
        """Get total number of checkpoints"""
        try:
            return self.checkpoints_collection.count_documents({})
        except PyMongoError as e:
            logger.error(f"Error counting checkpoints: {e}")
            return 0
    
    async def get_checkpoint_writes_count(self) -> int:
        """Get total number of checkpoint writes"""
        try:
            return self.checkpoint_writes_collection.count_documents({})
        except PyMongoError as e:
            logger.error(f"Error counting checkpoint writes: {e}")
            return 0
