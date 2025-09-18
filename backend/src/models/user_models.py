from pydantic import BaseModel, Field, validator
import re
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class User(BaseModel):
    """User entity model"""
    user_id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: Optional[str] = Field(None, description="User's full name")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="User status")
    created_at: datetime = Field(default_factory=datetime.now, description="User creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    preferences: Optional[dict] = Field(default_factory=dict, description="User preferences")
    
    @validator('email')
    def validate_email(cls, v):
        """Simple email validation"""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('username')
    def validate_username(cls, v):
        """Username validation"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.lower()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserSummary(BaseModel):
    """User summary for listing purposes"""
    user_id: str
    email: str
    username: str
    full_name: Optional[str]
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime]


class CreateUserRequest(BaseModel):
   
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: Optional[str] = Field(None, description="User's full name")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    preferences: Optional[dict] = Field(default_factory=dict, description="User preferences")
    
    @validator('email')
    def validate_email(cls, v):
        """Simple email validation"""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('username')
    def validate_username(cls, v):
        """Username validation"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.lower()


class UpdateUserRequest(BaseModel):
    """Request model for user updates"""
    full_name: Optional[str] = Field(None, description="User's full name")
    role: Optional[UserRole] = Field(None, description="User role")
    status: Optional[UserStatus] = Field(None, description="User status")
    preferences: Optional[dict] = Field(None, description="User preferences")


class UserResponse(BaseModel):
    """Response model for user operations"""
    success: bool
    data: Optional[User] = None
    message: str


class UserListResponse(BaseModel):
    """Response model for user list operations"""
    success: bool
    data: List[UserSummary]
    message: str
    total: int
