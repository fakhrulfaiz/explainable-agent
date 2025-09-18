from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from pymongo.errors import PyMongoError
import logging

from .base_repository import BaseRepository
from src.models.user_models import User, UserSummary, UserStatus, UserRole

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for user operations"""
    
    def __init__(self, database: Database):
        super().__init__(database, "users")
    
    def _create_indexes(self) -> None:
        """Create database indexes for efficient querying"""
        try:
            # Unique index on email
            self.collection.create_index("email", unique=True)
            # Unique index on username
            self.collection.create_index("username", unique=True)
            # Index on status for filtering
            self.collection.create_index("status")
            # Index on role for filtering
            self.collection.create_index("role")
            # Index on created_at for sorting
            self.collection.create_index([("created_at", -1)])
            # Index on last_login for sorting
            self.collection.create_index([("last_login", -1)])
        except PyMongoError as e:
            logger.warning(f"Could not create user indexes: {e}")
    
    def _to_entity(self, data: Dict[str, Any]) -> User:
        """Convert database document to User entity"""
        # Convert MongoDB _id to user_id for the entity
        if '_id' in data:
            data['user_id'] = str(data['_id'])
            del data['_id']
        return User(**data)
    
    def _to_document(self, entity: User) -> Dict[str, Any]:
        """Convert User entity to database document"""
        doc = entity.dict()
        # Remove user_id from document - MongoDB will use _id
        doc.pop('user_id', None)
        return doc
    
    async def find_by_user_id(self, user_id: str) -> Optional[User]:
        """Find user by user_id (MongoDB _id)"""
        return await self.find_by_id(user_id, "_id")
    
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email address"""
        return await self.find_by_id(email, "email")
    
    async def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        return await self.find_by_id(username, "username")
    
    async def create_user(self, user: User) -> bool:
        """Create a new user"""
        return await self.create(user)
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update user by user_id (MongoDB _id)"""
        update_data["updated_at"] = datetime.now()
        return await self.update_by_id(user_id, update_data, "_id")
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user by user_id (MongoDB _id)"""
        return await self.delete_by_id(user_id, "_id")
    
    async def update_last_login(self, user_id: str) -> bool:
        """Update user's last login time"""
        return await self.update_user(user_id, {"last_login": datetime.now()})
    
    async def update_status(self, user_id: str, status: UserStatus) -> bool:
        """Update user status"""
        return await self.update_user(user_id, {"status": status})
    
    async def get_users_by_role(self, role: UserRole, limit: int = 50, skip: int = 0) -> List[User]:
        """Get users by role with pagination"""
        return await self.find_many(
            {"role": role.value},
            limit=limit,
            skip=skip,
            sort_criteria=[("created_at", -1)]
        )
    
    async def get_users_by_status(self, status: UserStatus, limit: int = 50, skip: int = 0) -> List[User]:
        """Get users by status with pagination"""
        return await self.find_many(
            {"status": status.value},
            limit=limit,
            skip=skip,
            sort_criteria=[("created_at", -1)]
        )
    
    async def get_user_summaries(self, limit: int = 50, skip: int = 0, 
                                role_filter: Optional[UserRole] = None,
                                status_filter: Optional[UserStatus] = None) -> List[UserSummary]:
        """Get user summaries for listing purposes"""
        try:
            # Build filter criteria
            filter_criteria = {}
            if role_filter:
                filter_criteria["role"] = role_filter.value
            if status_filter:
                filter_criteria["status"] = status_filter.value
            
            # Project only needed fields for summary
            projection = {
                "user_id": 1,
                "email": 1,
                "username": 1,
                "full_name": 1,
                "role": 1,
                "status": 1,
                "created_at": 1,
                "last_login": 1
            }
            
            cursor = self.collection.find(
                filter_criteria,
                projection
            ).sort("created_at", -1).skip(skip).limit(limit)
            
            summaries = []
            async for user_data in cursor:
                user_data.pop('_id', None)  # Remove MongoDB's _id field
                summary = UserSummary(**user_data)
                summaries.append(summary)
            
            return summaries
            
        except PyMongoError as e:
            logger.error(f"Error retrieving user summaries: {e}")
            raise Exception(f"Failed to retrieve user summaries: {e}")
    
    async def count_users(self, role_filter: Optional[UserRole] = None,
                         status_filter: Optional[UserStatus] = None) -> int:
        """Get total number of users with optional filters"""
        filter_criteria = {}
        if role_filter:
            filter_criteria["role"] = role_filter.value
        if status_filter:
            filter_criteria["status"] = status_filter.value
        
        return await self.count(filter_criteria)
    
    async def search_users(self, search_term: str, limit: int = 50, skip: int = 0) -> List[User]:
        """Search users by username, email, or full name"""
        try:
            # Create regex pattern for case-insensitive search
            regex_pattern = {"$regex": search_term, "$options": "i"}
            
            filter_criteria = {
                "$or": [
                    {"username": regex_pattern},
                    {"email": regex_pattern},
                    {"full_name": regex_pattern}
                ]
            }
            
            return await self.find_many(
                filter_criteria,
                limit=limit,
                skip=skip,
                sort_criteria=[("username", 1)]
            )
            
        except PyMongoError as e:
            logger.error(f"Error searching users: {e}")
            raise Exception(f"Failed to search users: {e}")
    
    async def check_email_exists(self, email: str, exclude_user_id: Optional[str] = None) -> bool:
        """Check if email already exists (excluding current user for updates)"""
        try:
            filter_criteria = {"email": email}
            if exclude_user_id:
                filter_criteria["user_id"] = {"$ne": exclude_user_id}
            
            count = await self.count(filter_criteria)
            return count > 0
            
        except PyMongoError as e:
            logger.error(f"Error checking email existence: {e}")
            return False
    
    async def check_username_exists(self, username: str, exclude_user_id: Optional[str] = None) -> bool:
        """Check if username already exists (excluding current user for updates)"""
        try:
            filter_criteria = {"username": username}
            if exclude_user_id:
                filter_criteria["user_id"] = {"$ne": exclude_user_id}
            
            count = await self.count(filter_criteria)
            return count > 0
            
        except PyMongoError as e:
            logger.error(f"Error checking username existence: {e}")
            return False
