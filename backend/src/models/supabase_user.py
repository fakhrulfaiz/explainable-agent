from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class SupabaseUser(BaseModel):
    user_id: str = Field(..., description="Supabase user ID (sub claim)")
    email: str = Field(..., description="User email address")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    phone_verified: bool = Field(default=False, description="Whether phone is verified")
    last_sign_in: Optional[datetime] = Field(None, description="Last sign in time")
    created_at: Optional[datetime] = Field(None, description="Account creation time")
    provider: str = Field(default="email", description="Auth provider")
    
    # Optional metadata from user_metadata
    full_name: Optional[str] = Field(None, description="User's full name")
    avatar_url: Optional[str] = Field(None, description="User's avatar URL")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User preferences")

    @classmethod
    def from_jwt_payload(cls, payload: Dict[str, Any]) -> "SupabaseUser":
        """Create SupabaseUser from JWT token payload"""
        user_metadata = payload.get("user_metadata", {})
        app_metadata = payload.get("app_metadata", {})
        
        # Handle timestamp conversion with better error handling
        def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
            if not timestamp_str:
                return None
            try:
                return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        
        # Use iat (issued at) as fallback for last_sign_in if last_sign_in_at not available
        last_sign_in_timestamp = payload.get("last_sign_in_at")
        if not last_sign_in_timestamp and payload.get("iat"):
            last_sign_in_timestamp = datetime.fromtimestamp(payload["iat"])
        else:
            last_sign_in_timestamp = parse_timestamp(last_sign_in_timestamp)
        
        return cls(
            user_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            role=UserRole(user_metadata.get("role", "user")),
            email_verified=user_metadata.get("email_verified", False),
            phone_verified=user_metadata.get("phone_verified", False),
            last_sign_in=last_sign_in_timestamp,
            created_at=parse_timestamp(payload.get("created_at", "")),
            provider=app_metadata.get("provider", "email"),
            full_name=user_metadata.get("full_name"),
            avatar_url=user_metadata.get("avatar_url"),
            preferences=user_metadata.get("preferences", {})
        )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserActivity(BaseModel):
    """
    Model for tracking user activity in our system
    This is stored in our database for analytics
    """
    id: Optional[str] = Field(None, description="Activity ID")
    user_id: str = Field(..., description="Supabase user ID")
    action: str = Field(..., description="Action performed (e.g., 'query', 'chat', 'approval')")
    resource: Optional[str] = Field(None, description="Resource accessed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Activity timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional activity data")
    ip_address: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserSession(BaseModel):
    """
    Model for tracking active user sessions
    """
    user_id: str = Field(..., description="Supabase user ID")
    session_id: str = Field(..., description="Session identifier")
    started_at: datetime = Field(default_factory=datetime.now, description="Session start time")
    last_activity: datetime = Field(default_factory=datetime.now, description="Last activity time")
    ip_address: Optional[str] = Field(None, description="Session IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    is_active: bool = Field(default=True, description="Whether session is active")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
