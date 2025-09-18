from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from src.repositories.checkpoint_repository import (
    CheckpointWriteRepository, 
    CheckpointRepository,
    CheckpointWriteEntry,
    CheckpointEntry
)

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service for managing checkpoint operations using repository pattern"""
    
    def __init__(self, 
                 checkpoint_write_repo: CheckpointWriteRepository,
                 checkpoint_repo: CheckpointRepository):
        self.checkpoint_write_repo = checkpoint_write_repo
        self.checkpoint_repo = checkpoint_repo
    
    
    # Checkpoint Writes Operations
    async def add_checkpoint_write(self, checkpoint_id: str, data: Dict[str, Any], thread_id: str = None) -> bool:
        """Add a new checkpoint write entry"""
        try:
            write_entry = CheckpointWriteEntry(
                checkpoint_id=checkpoint_id,
                data=data,
                thread_id=thread_id
            )
            
            success = await self.checkpoint_write_repo.create_checkpoint_write(write_entry)
            
            if success:
                logger.info(f"Added checkpoint write for checkpoint_id: {checkpoint_id}")
            else:
                logger.warning(f"Failed to add checkpoint write for checkpoint_id: {checkpoint_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error adding checkpoint write for {checkpoint_id}: {e}")
            raise Exception(f"Failed to add checkpoint write: {e}")
    
    async def delete_checkpoint_writes_by_thread(self, thread_id: str) -> int:
        """Delete all checkpoint writes for a specific thread_id"""
        try:
            deleted_count = await self.checkpoint_write_repo.delete_by_thread_id(thread_id)
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting checkpoint writes for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes for thread: {e}")
    
    async def delete_checkpoint_write(self, checkpoint_id: str) -> bool:
        """Delete checkpoint write entries by checkpoint_id"""
        try:
            deleted_count = await self.checkpoint_write_repo.delete_by_checkpoint_id(checkpoint_id)
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} checkpoint write(s) for checkpoint_id: {checkpoint_id}")
                return True
            else:
                logger.warning(f"No checkpoint writes found for checkpoint_id: {checkpoint_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting checkpoint writes for {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete checkpoint writes: {e}")
    
    async def delete_checkpoint_write_by_id(self, write_id: str) -> bool:
        """Delete a specific checkpoint write entry by its MongoDB ObjectId"""
        try:
            success = await self.checkpoint_write_repo.delete_by_object_id(write_id)
            
            if success:
                logger.info(f"Deleted checkpoint write with id: {write_id}")
            else:
                logger.warning(f"Checkpoint write not found with id: {write_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error deleting checkpoint write {write_id}: {e}")
            raise Exception(f"Failed to delete checkpoint write: {e}")
    
    async def get_checkpoint_writes(self, checkpoint_id: str, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Get all checkpoint write entries for a specific checkpoint_id"""
        try:
            write_entries = await self.checkpoint_write_repo.find_by_checkpoint_id(checkpoint_id, limit, skip)
            
            writes = []
            for entry in write_entries:
                writes.append(entry.dict())
            
            logger.info(f"Retrieved {len(writes)} checkpoint writes for checkpoint_id: {checkpoint_id}")
            return writes
            
        except Exception as e:
            logger.error(f"Error retrieving checkpoint writes for {checkpoint_id}: {e}")
            raise Exception(f"Failed to retrieve checkpoint writes: {e}")
    
    # Checkpoints Operations
    async def add_checkpoint(self, checkpoint_id: str, checkpoint_data: Dict[str, Any], thread_id: str = None) -> bool:
        try:
            checkpoint_entry = CheckpointEntry(
                checkpoint_id=checkpoint_id,
                checkpoint_data=checkpoint_data,
                thread_id=thread_id
            )
            
            success = await self.checkpoint_repo.create_checkpoint(checkpoint_entry)
            
            if success:
                logger.info(f"Added checkpoint: {checkpoint_id}")
            else:
                logger.warning(f"Failed to add checkpoint: {checkpoint_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error adding checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to add checkpoint: {e}")
    
    async def delete_checkpoints_by_thread(self, thread_id: str) -> int:
        try:
            deleted_count = await self.checkpoint_repo.delete_by_thread_id(thread_id)
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting checkpoints for thread {thread_id}: {e}")
            raise Exception(f"Failed to delete checkpoints for thread: {e}")
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        try:
            success = await self.checkpoint_repo.delete_by_checkpoint_id(checkpoint_id)
            
            if success:
                logger.info(f"Deleted checkpoint: {checkpoint_id}")
            else:
                logger.warning(f"Checkpoint not found: {checkpoint_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error deleting checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to delete checkpoint: {e}")
    
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        try:
            checkpoint_entry = await self.checkpoint_repo.find_by_checkpoint_id(checkpoint_id)
            
            if checkpoint_entry:
                logger.info(f"Retrieved checkpoint: {checkpoint_id}")
                return checkpoint_entry.dict()
            else:
                logger.info(f"Checkpoint not found: {checkpoint_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving checkpoint {checkpoint_id}: {e}")
            raise Exception(f"Failed to retrieve checkpoint: {e}")
    
    async def get_all_checkpoints(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        try:
            checkpoint_entries = await self.checkpoint_repo.get_all_checkpoints(limit, skip)
            
            checkpoints = []
            for entry in checkpoint_entries:
                checkpoints.append(entry.dict())
            
            logger.info(f"Retrieved {len(checkpoints)} checkpoints")
            return checkpoints
            
        except Exception as e:
            logger.error(f"Error retrieving checkpoints: {e}")
            raise Exception(f"Failed to retrieve checkpoints: {e}")
    
    # Utility Operations
    async def delete_all_checkpoint_data(self, checkpoint_id: str) -> Dict[str, bool]:
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
        try:
            return await self.checkpoint_repo.count()
        except Exception as e:
            logger.error(f"Error counting checkpoints: {e}")
            return 0
    
    async def get_checkpoint_writes_count(self) -> int:
        try:
            return await self.checkpoint_write_repo.count()
        except Exception as e:
            logger.error(f"Error counting checkpoint writes: {e}")
            return 0
