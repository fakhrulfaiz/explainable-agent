from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from src.services.user_service import UserService
from src.repositories.dependencies import get_user_service
from src.models.user_models import (
    UserResponse,
    UserListResponse,
    CreateUserRequest,
    UpdateUserRequest,
    User,
    UserRole,
    UserStatus
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Create a new user"""
    try:
        user = await user_service.create_user(request)
        return UserResponse(
            success=True,
            data=user,
            message="User created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=UserListResponse)
async def get_all_users(
    limit: int = Query(50, ge=1, le=100, description="Number of users to return"),
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    user_service: UserService = Depends(get_user_service)
):
    """Get all users with pagination"""
    try:
        users = await user_service.get_all_users(limit=limit, skip=skip)
        total = await user_service.get_user_count()
        
        return UserListResponse(
            success=True,
            data=users,
            message=f"Retrieved {len(users)} users",
            total=total
        )
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    """Get a specific user by ID"""
    try:
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            success=True,
            data=user,
            message="User retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: str,
    user_service: UserService = Depends(get_user_service)
):
    """Get a user by email address"""
    try:
        user = await user_service.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            success=True,
            data=user,
            message="User retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user by email {email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    """Delete a user"""
    try:
        success = await user_service.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
