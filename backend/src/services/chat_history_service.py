from typing import List, Optional
from datetime import datetime
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from src.models.database import get_mongodb
from pymongo.database import Database
from src.models.chat_models import (
    ChatThread, 
    ChatMessage, 
    ChatThreadSummary,
    CreateChatRequest,
    AddMessageRequest
)
from src.services.checkpoint_service import CheckpointService
import logging

logger = logging.getLogger(__name__)

class ChatHistoryService:
    
    def __init__(self, database: Database):
        self.db = database
        self.collection: Collection = self.db.chat_threads
        # Initialize checkpoint service for cleanup operations
        self.checkpoint_service = CheckpointService(database)
        # Create indexes for better performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for efficient querying"""
        try:
            # Index on thread_id for fast lookups
            self.collection.create_index("thread_id", unique=True)
            # Index on updated_at for sorting by recency
            self.collection.create_index([("updated_at", -1)])
            # Index on created_at for sorting by creation time
            self.collection.create_index([("created_at", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create indexes: {e}")
    
    async def create_thread(self, request: CreateChatRequest) -> ChatThread:
     
        try:
            # Generate thread_id if not provided
            import uuid
            thread_id = str(uuid.uuid4())
            
            # Create thread object
            thread = ChatThread(
                thread_id=thread_id,
                title=request.title or "New Chat",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Add initial message if provided
            if request.initial_message:
                initial_msg = ChatMessage(
                    sender="user",
                    content=request.initial_message,
                    timestamp=datetime.now()
                )
                thread.messages.append(initial_msg)
            
            # Insert into database
            thread_dict = thread.dict()
            self.collection.insert_one(thread_dict)
            
            logger.info(f"Created new chat thread: {thread_id}")
            return thread
            
        except PyMongoError as e:
            logger.error(f"Error creating chat thread: {e}")
            raise Exception(f"Failed to create chat thread: {e}")
    
    async def get_thread(self, thread_id: str) -> Optional[ChatThread]:
      
        try:
            thread_data = self.collection.find_one({"thread_id": thread_id})
            if thread_data:
                # Remove MongoDB's _id field
                thread_data.pop('_id', None)
                return ChatThread(**thread_data)
            return None
            
        except PyMongoError as e:
            logger.error(f"Error retrieving chat thread {thread_id}: {e}")
            raise Exception(f"Failed to retrieve chat thread: {e}")
    
    async def add_message(self, request: AddMessageRequest) -> bool:
      
        try:
            message = ChatMessage(
                sender=request.sender,
                content=request.content,
                timestamp=datetime.now(),
                message_type=request.message_type,
                checkpoint_id=request.checkpoint_id
            )
            
            result = self.collection.update_one(
                {"thread_id": request.thread_id},
                {
                    "$push": {"messages": message.dict()},
                    "$set": {"updated_at": datetime.now()}
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Added message to thread {request.thread_id}")
                return True
            else:
                logger.warning(f"Thread {request.thread_id} not found")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error adding message to thread {request.thread_id}: {e}")
            raise Exception(f"Failed to add message: {e}")
    
    async def get_all_threads(self, limit: int = 50, skip: int = 0) -> List[ChatThreadSummary]:
        try:
            cursor = self.collection.find(
                {},
                {
                    "thread_id": 1,
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "messages": {"$slice": -1}  # Get only the last message
                }
            ).sort("updated_at", -1).skip(skip).limit(limit)
            
            threads = []
            for thread_data in cursor:
                # Extract last message preview
                last_message = None
                message_count = 0
                
                if "messages" in thread_data and thread_data["messages"]:
                    last_msg = thread_data["messages"][-1]
                    last_message = last_msg.get("content", "")[:100]  # First 100 chars
                    if len(last_msg.get("content", "")) > 100:
                        last_message += "..."
                
                # Get total message count
                count_result = self.collection.find_one(
                    {"thread_id": thread_data["thread_id"]},
                    {"messages": 1}
                )
                if count_result and "messages" in count_result:
                    message_count = len(count_result["messages"])
                
                summary = ChatThreadSummary(
                    thread_id=thread_data["thread_id"],
                    title=thread_data.get("title", "Untitled Chat"),
                    last_message=last_message,
                    message_count=message_count,
                    created_at=thread_data["created_at"],
                    updated_at=thread_data["updated_at"]
                )
                threads.append(summary)
            
            return threads
            
        except PyMongoError as e:
            logger.error(f"Error retrieving chat threads: {e}")
            raise Exception(f"Failed to retrieve chat threads: {e}")
    
    async def delete_thread(self, thread_id: str) -> bool:
        try:
            result = self.collection.delete_one({"thread_id": thread_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted chat thread: {thread_id}")
                
                # Also delete associated checkpoint data
                try:
                    checkpoint_result = await self.checkpoint_service.delete_all_thread_data(thread_id)
                    total_deleted = checkpoint_result.get('total_deleted', 0)
                    if total_deleted > 0:
                        logger.info(f"Deleted {total_deleted} checkpoint records for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete checkpoint data for thread {thread_id}: {e}")
                    # Don't fail the whole operation if checkpoint cleanup fails
                
                return True
            else:
                logger.warning(f"Thread {thread_id} not found for deletion")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error deleting chat thread {thread_id}: {e}")
            raise Exception(f"Failed to delete chat thread: {e}")
    
    async def update_thread_title(self, thread_id: str, title: str) -> bool:
        """Update the title of a chat thread"""
        try:
            result = self.collection.update_one(
                {"thread_id": thread_id},
                {
                    "$set": {
                        "title": title,
                        "updated_at": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated title for thread {thread_id}")
                return True
            else:
                logger.warning(f"Thread {thread_id} not found for title update")
                return False
                
        except PyMongoError as e:
            logger.error(f"Error updating thread title {thread_id}: {e}")
            raise Exception(f"Failed to update thread title: {e}")
    
    async def get_thread_count(self) -> int:
        """Get total number of chat threads"""
        try:
            return self.collection.count_documents({})
        except PyMongoError as e:
            logger.error(f"Error counting chat threads: {e}")
            return 0


# Note: This service is now used with dependency injection
# Remove the global instance as it's no longer needed
