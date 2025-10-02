from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    
    def __init__(self, database: Database, collection_name: str):
        self.db = database
        self.collection: Collection = self.db[collection_name]
        self._create_indexes()
    
    @abstractmethod
    def _create_indexes(self) -> None:
        pass
    
    @abstractmethod
    def _to_entity(self, data: Dict[str, Any]) -> T:
        pass
    
    @abstractmethod
    def _to_document(self, entity: T) -> Dict[str, Any]:
        pass
    
    async def create(self, entity: T) -> bool:
        try:
            document = self._to_document(entity)
            result = await self.collection.insert_one(document)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error creating document: {e}")
            raise Exception(f"Failed to create document: {e}")
    
    async def find_by_id(self, entity_id: str, id_field: str = "_id") -> Optional[T]:
        try:
            document = await self.collection.find_one({id_field: entity_id})
            if document:
                if id_field != "_id":
                    document.pop('_id', None)
                return self._to_entity(document)
            return None
        except PyMongoError as e:
            logger.error(f"Error finding document by {id_field}={entity_id}: {e}")
            raise Exception(f"Failed to find document: {e}")
    
    async def update_by_id(self, entity_id: str, update_data: Dict[str, Any], id_field: str = "_id") -> bool:
        try:
            result = await self.collection.update_one(
                {id_field: entity_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error updating document {id_field}={entity_id}: {e}")
            raise Exception(f"Failed to update document: {e}")
    
    async def delete_by_id(self, entity_id: str, id_field: str = "_id") -> bool:
        try:
            result = await self.collection.delete_one({id_field: entity_id})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Error deleting document {id_field}={entity_id}: {e}")
            raise Exception(f"Failed to delete document: {e}")
    
    async def delete_many(self, filter_criteria: Dict[str, Any]) -> int:
        """Delete multiple documents matching the filter criteria"""
        try:
            result = await self.collection.delete_many(filter_criteria)
            logger.info(f"Deleted {result.deleted_count} documents")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error deleting documents: {e}")
            raise Exception(f"Failed to delete documents: {e}")
    
    async def find_many(self, filter_criteria: Dict[str, Any] = None, 
                       limit: int = None, skip: int = None, 
                       sort_criteria: List[tuple] = None) -> List[T]:
        try:
            filter_criteria = filter_criteria or {}
            cursor = self.collection.find(filter_criteria)
            
            if sort_criteria:
                cursor = cursor.sort(sort_criteria)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            
            documents = []
            async for doc in cursor:
                doc.pop('_id', None)
                documents.append(self._to_entity(doc))
            
            return documents
        except PyMongoError as e:
            logger.error(f"Error finding documents: {e}")
            raise Exception(f"Failed to find documents: {e}")
    
    async def count(self, filter_criteria: Dict[str, Any] = None) -> int:
        try:
            filter_criteria = filter_criteria or {}
            return await self.collection.count_documents(filter_criteria)
        except PyMongoError as e:
            logger.error(f"Error counting documents: {e}")
            return 0
