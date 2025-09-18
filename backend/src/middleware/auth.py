from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import httpx
import os
from functools import lru_cache
import logging

from src.models.supabase_user import SupabaseUser

logger = logging.getLogger(__name__)
security = HTTPBearer()


class SupabaseAuth:
   
    
    def __init__(self):
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET") 
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        if not self.supabase_jwt_secret and self.environment == "production":
            logger.warning("SUPABASE_JWT_SECRET not set - using development mode")

    async def verify_token(self, token: str) -> dict:
   
        try:
            # For development, skip signature verification
            if self.environment == "development":
                logger.debug("Development mode: skipping JWT signature verification")
                payload = jwt.decode(token, options={"verify_signature": False})
                return payload
            
            # For production, verify with Supabase JWT secret
            if not self.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="JWT secret not configured"
                )
            
            payload = jwt.decode(
                token,
                self.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            
            logger.debug(f"Token verified for user: {payload.get('email')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Expired JWT token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed"
            )


    async def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> SupabaseUser:
        """Get current user from JWT token"""
        payload = await self.verify_token(credentials.credentials)
        return SupabaseUser.from_jwt_payload(payload)
    


# Global instance
supabase_auth = SupabaseAuth()


# Dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> SupabaseUser:
    """Dependency to get current authenticated user"""
    return await supabase_auth.get_current_user(credentials)


async def get_optional_user(request: Request) -> Optional[SupabaseUser]:
    """Optional authentication - returns None if no token or invalid token"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_current_user(credentials)
    except HTTPException:
        # Auth failed, but that's OK for optional auth
        return None
    except Exception as e:
        logger.warning(f"Optional auth error: {str(e)}")
        return None


async def require_role(required_role: str):
    """Dependency factory for role-based access control"""
    async def check_role(current_user: SupabaseUser = Depends(get_current_user)) -> SupabaseUser:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role}"
            )
        return current_user
    return check_role


# Common role dependencies
async def require_admin(current_user: SupabaseUser = Depends(get_current_user)) -> SupabaseUser:
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_moderator_or_admin(current_user: SupabaseUser = Depends(get_current_user)) -> SupabaseUser:
    """Require moderator or admin role"""
    if current_user.role not in ["moderator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin access required"
        )
    return current_user