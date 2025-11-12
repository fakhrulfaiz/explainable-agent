import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError

from .base_repository import BaseRepository
from src.models.chat_models import MessageContent

logger = logging.getLogger(__name__)

class MessageContentRepository(BaseRepository[MessageContent]):
    
    def __init__(self, database: Database):
        super().__init__(database, "message_content")
    
    async def _create_indexes(self) -> None:
        try:
            # Core indexes for efficient lookups
            await self.collection.create_index("message_id", name="idx_message_id")
            await self.collection.create_index("block_id", unique=True, name="idx_block_id_unique")
            
            # Compound index for efficient message-based queries with ordering
            await self.collection.create_index([("message_id", 1), ("created_at", 1)], name="idx_message_created")
            
            # Index for block type filtering
            await self.collection.create_index("type", name="idx_type")
            
            logger.info("Successfully created message_content indexes")
        except PyMongoError as e:
            logger.warning(f"Could not create message_content indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> MessageContent:
        return MessageContent(**data)
    
    def _to_document(self, entity: MessageContent) -> Dict[str, Any]:
        return entity.dict()
    
    async def add_content_blocks(self, message_id: int, blocks: List[Dict[str, Any]]) -> bool:
        """
        Bulk insert content blocks for a message.
        Blocks should have: id, type, needsApproval (or needs_approval), data
        """
        try:
            if not blocks:
                return True  # No blocks to insert
            
            documents = []
            for block in blocks:
                # Normalize field names (handle both needsApproval and needs_approval)
                needs_approval = block.get('needsApproval', block.get('needs_approval', False))
                block_id = block.get('id', block.get('block_id'))
                block_type = block.get('type')
                block_data = block.get('data', {})
                # Handle message_status (can be from frontend as messageStatus or message_status)
                message_status = block.get('messageStatus', block.get('message_status', None))
                
                if not block_id or not block_type:
                    logger.warning(f"Skipping block with missing id or type: {block}")
                    continue
                
                message_content = MessageContent(
                    message_id=message_id,
                    block_id=block_id,
                    type=block_type,
                    needs_approval=needs_approval,
                    message_status=message_status,
                    data=block_data,
                    created_at=datetime.now()
                )
                documents.append(self._to_document(message_content))
            
            if documents:
                result = await self.collection.insert_many(documents)
                logger.info(f"Inserted {len(result.inserted_ids)} content blocks for message {message_id}")
                return len(result.inserted_ids) > 0
            return True
        except PyMongoError as e:
            logger.error(f"Error adding content blocks for message {message_id}: {e}")
            raise Exception(f"Failed to add content blocks: {e}")
    
    async def get_blocks_by_message_id(self, message_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve all content blocks for a message, ordered by created_at.
        Returns blocks in the format expected by frontend: {id, type, needsApproval, data}
        """
        try:
            documents = await self.find_many(
                filter_criteria={"message_id": message_id},
                sort_criteria=[("created_at", 1)]  # Ascending order
            )
            
            # Convert to frontend format
            blocks = []
            for doc in documents:
                blocks.append({
                    "id": doc.block_id,
                    "type": doc.type,
                    "needsApproval": doc.needs_approval,
                    "messageStatus": getattr(doc, 'message_status', None),
                    "data": doc.data
                })
            
            return blocks
        except PyMongoError as e:
            logger.error(f"Error retrieving blocks for message {message_id}: {e}")
            raise Exception(f"Failed to retrieve content blocks: {e}")
    
    async def update_block(self, block_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a content block by block_id.
        Updates can include: needs_approval, message_status, data
        """
        try:
            # Normalize field names for updates
            normalized_updates = {}
            
            # Handle needsApproval (can be from frontend as needsApproval or needs_approval)
            if 'needsApproval' in updates:
                normalized_updates['needs_approval'] = updates['needsApproval']
            if 'needs_approval' in updates:
                normalized_updates['needs_approval'] = updates['needs_approval']
            
            # Handle message_status (can be from frontend as messageStatus or message_status)
            if 'messageStatus' in updates:
                normalized_updates['message_status'] = updates['messageStatus']
            if 'message_status' in updates:
                normalized_updates['message_status'] = updates['message_status']
            
            # If message_status is set to approved or rejected, set needs_approval to False
            if 'message_status' in normalized_updates:
                status = normalized_updates['message_status']
                if status in ['approved', 'rejected']:
                    normalized_updates['needs_approval'] = False
                elif status == 'pending':
                    normalized_updates['needs_approval'] = True
            
            # Handle data updates
            if 'data' in updates:
                normalized_updates['data'] = updates['data']
            
            if not normalized_updates:
                logger.warning(f"No valid updates provided for block {block_id}")
                return False
            
            result = await self.collection.update_one(
                {"block_id": block_id},
                {"$set": normalized_updates}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated block {block_id} with fields: {list(normalized_updates.keys())}")
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error updating block {block_id}: {e}")
            raise Exception(f"Failed to update block: {e}")
    
    async def delete_blocks_by_message_id(self, message_id: int) -> int:
        """
        Delete all content blocks for a message (cleanup operation).
        Returns the number of deleted blocks.
        """
        try:
            result = await self.delete_many({"message_id": message_id})
            logger.info(f"Deleted {result} content blocks for message {message_id}")
            return result
        except PyMongoError as e:
            logger.error(f"Error deleting blocks for message {message_id}: {e}")
            raise Exception(f"Failed to delete content blocks: {e}")
    
    async def get_block_by_id(self, block_id: str) -> Optional[MessageContent]:
        """Get a single content block by block_id"""
        try:
            return await self.find_by_id(block_id, id_field="block_id")
        except Exception as e:
            logger.error(f"Error finding block {block_id}: {e}")
            return None

