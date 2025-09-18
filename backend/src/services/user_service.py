from typing import List, Optional
from datetime import datetime
import uuid
import logging

from src.repositories.user_repository import UserRepository
from src.models.user_models import (
    User, 
    UserSummary, 
    CreateUserRequest,
    UpdateUserRequest,
    UserRole,
    UserStatus
)

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users using repository pattern"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    async def create_user(self, request: CreateUserRequest) -> User:
        """Create a new user"""
        try:
            # Check if email already exists
            if await self.user_repo.check_email_exists(request.email):
                raise Exception(f"Email {request.email} already exists")
            
            # Check if username already exists
            if await self.user_repo.check_username_exists(request.username):
                raise Exception(f"Username {request.username} already exists")
            
            # Create user object (MongoDB will generate _id)
            user = User(
                user_id="",  # Will be set by repository from MongoDB _id
                email=request.email,
                username=request.username,
                full_name=request.full_name,
                role=request.role,
                status=UserStatus.ACTIVE,
                preferences=request.preferences or {},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Save using repository
            success = await self.user_repo.create_user(user)
            if not success:
                raise Exception("Failed to create user in database")
            
            logger.info(f"Created new user: {user.user_id} ({request.email})")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise Exception(f"Failed to create user: {e}")
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        try:
            return await self.user_repo.find_by_user_id(user_id)
        except Exception as e:
            logger.error(f"Error retrieving user {user_id}: {e}")
            raise Exception(f"Failed to retrieve user: {e}")
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email"""
        try:
            return await self.user_repo.find_by_email(email)
        except Exception as e:
            logger.error(f"Error retrieving user by email {email}: {e}")
            raise Exception(f"Failed to retrieve user: {e}")
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username"""
        try:
            return await self.user_repo.find_by_username(username)
        except Exception as e:
            logger.error(f"Error retrieving user by username {username}: {e}")
            raise Exception(f"Failed to retrieve user: {e}")
    
    async def update_user(self, user_id: str, request: UpdateUserRequest) -> bool:
        """Update user information"""
        try:
            # Check if user exists
            existing_user = await self.user_repo.find_by_user_id(user_id)
            if not existing_user:
                raise Exception(f"User {user_id} not found")
            
            # Build update data (only include fields that are provided)
            update_data = {}
            if request.full_name is not None:
                update_data["full_name"] = request.full_name
            if request.role is not None:
                update_data["role"] = request.role
            if request.status is not None:
                update_data["status"] = request.status
            if request.preferences is not None:
                update_data["preferences"] = request.preferences
            
            if not update_data:
                logger.warning(f"No update data provided for user {user_id}")
                return True  # Nothing to update is considered success
            
            # Update user
            success = await self.user_repo.update_user(user_id, update_data)
            if success:
                logger.info(f"Updated user: {user_id}")
            else:
                logger.warning(f"User {user_id} not found for update")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise Exception(f"Failed to update user: {e}")
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        try:
            success = await self.user_repo.delete_user(user_id)
            if success:
                logger.info(f"Deleted user: {user_id}")
            else:
                logger.warning(f"User {user_id} not found for deletion")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            raise Exception(f"Failed to delete user: {e}")
    
    async def update_user_status(self, user_id: str, status: UserStatus) -> bool:
        """Update user status"""
        try:
            success = await self.user_repo.update_status(user_id, status)
            if success:
                logger.info(f"Updated user {user_id} status to {status}")
            else:
                logger.warning(f"User {user_id} not found for status update")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating user status {user_id}: {e}")
            raise Exception(f"Failed to update user status: {e}")
    
    async def record_login(self, user_id: str) -> bool:
        """Record user login timestamp"""
        try:
            success = await self.user_repo.update_last_login(user_id)
            if success:
                logger.info(f"Recorded login for user: {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording login for user {user_id}: {e}")
            raise Exception(f"Failed to record login: {e}")
    
    async def get_all_users(self, limit: int = 50, skip: int = 0,
                           role_filter: Optional[UserRole] = None,
                           status_filter: Optional[UserStatus] = None) -> List[UserSummary]:
        """Get all users with optional filtering and pagination"""
        try:
            return await self.user_repo.get_user_summaries(
                limit=limit, 
                skip=skip,
                role_filter=role_filter,
                status_filter=status_filter
            )
        except Exception as e:
            logger.error(f"Error retrieving users: {e}")
            raise Exception(f"Failed to retrieve users: {e}")
    
    async def search_users(self, search_term: str, limit: int = 50, skip: int = 0) -> List[User]:
        """Search users by username, email, or full name"""
        try:
            if not search_term or len(search_term.strip()) < 2:
                raise Exception("Search term must be at least 2 characters long")
            
            return await self.user_repo.search_users(search_term.strip(), limit, skip)
            
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            raise Exception(f"Failed to search users: {e}")
    
    async def get_users_by_role(self, role: UserRole, limit: int = 50, skip: int = 0) -> List[User]:
        """Get users by role"""
        try:
            return await self.user_repo.get_users_by_role(role, limit, skip)
        except Exception as e:
            logger.error(f"Error retrieving users by role {role}: {e}")
            raise Exception(f"Failed to retrieve users by role: {e}")
    
    async def get_users_by_status(self, status: UserStatus, limit: int = 50, skip: int = 0) -> List[User]:
        """Get users by status"""
        try:
            return await self.user_repo.get_users_by_status(status, limit, skip)
        except Exception as e:
            logger.error(f"Error retrieving users by status {status}: {e}")
            raise Exception(f"Failed to retrieve users by status: {e}")
    
    async def get_user_count(self, role_filter: Optional[UserRole] = None,
                            status_filter: Optional[UserStatus] = None) -> int:
        """Get total number of users with optional filters"""
        try:
            return await self.user_repo.count_users(role_filter, status_filter)
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
    
    async def suspend_user(self, user_id: str) -> bool:
        """Suspend a user account"""
        return await self.update_user_status(user_id, UserStatus.SUSPENDED)
    
    async def activate_user(self, user_id: str) -> bool:
        """Activate a user account"""
        return await self.update_user_status(user_id, UserStatus.ACTIVE)
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account"""
        return await self.update_user_status(user_id, UserStatus.INACTIVE)
