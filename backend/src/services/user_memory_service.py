"""
User Memory Service - Manages long-term memory, user profiles, and per-user LLM configuration
via Supabase profiles table
"""
from typing import Dict, Any, Optional, TypedDict, Literal
from datetime import datetime
from dataclasses import dataclass
import logging
import os

import httpx

from src.models.config import settings


logger = logging.getLogger(__name__)

# Valid communication styles
CommunicationStyle = Literal["concise", "detailed", "balanced", "technical", "casual", "formal"]
VALID_COMMUNICATION_STYLES = ["concise", "detailed", "balanced", "technical", "casual", "formal"]


class UserProfile(TypedDict):
    """User profile structure stored in Supabase profiles table"""

    name: str
    email: str
    llm_provider: str  # "openai", "ollama", "deepseek", "groq"
    llm_model: str  # Model name
    communication_style: CommunicationStyle
    preferences: Dict[str, Any]
    created_at: str
    updated_at: str


@dataclass
class UserContext:
    """Runtime context for user identification"""
    user_id: str


class UserMemoryService:
    """Service for managing user profiles backed by Supabase profiles table"""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        config_supabase_url = getattr(settings, "supabase_url", "") or ""
        config_service_role_key = getattr(settings, "supabase_service_role_key", "") or ""

        resolved_url = supabase_url or config_supabase_url or os.getenv("SUPABASE_URL", "")
        resolved_key = (
            service_role_key
            or config_service_role_key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )

        self.supabase_url = resolved_url.rstrip("/") if resolved_url else ""
        self.service_role_key = resolved_key
        self.client = client or httpx.Client(timeout=10.0)

        if not self.is_configured:
            logger.warning(
                "UserMemoryService is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to enable profile storage."
            )
        else:
            logger.info("UserMemoryService initialized with Supabase backend")

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    @property
    def rest_api_base(self) -> str:
        if not self.is_configured:
            raise RuntimeError("Supabase credentials are not configured")
        return f"{self.supabase_url}/rest/v1"

    def _headers(self) -> Dict[str, str]:
        if not self.is_configured:
            raise RuntimeError("Supabase credentials are not configured")
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _rest_request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        try:
            response = self.client.request(
                method,
                f"{self.rest_api_base}{path}",
                headers=self._headers(),
                json=json,
                params=params,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Supabase REST request failed (%s %s): %s", method, path, exc.response.text
            )
            raise
        except Exception as exc:
            logger.error("Supabase REST request error (%s %s): %s", method, path, exc)
            raise

    def _fetch_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured:
            logger.error("Cannot fetch profile; credentials not configured")
            return None
        try:
            result = self._rest_request("GET", f"/profiles?id=eq.{user_id}&select=*")
            if result and len(result) > 0:
                return result[0]
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Profile for user %s not found", user_id)
                return None
            raise

    def _upsert_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        if not self.is_configured:
            logger.error("Cannot upsert profile; credentials not configured")
            return False
        try:
            profile_data["id"] = user_id
            # Use upsert with on_conflict to handle existing profiles
            headers = self._headers()
            headers["Prefer"] = "resolution=merge-duplicates"
            
            response = self.client.request(
                "POST",
                f"{self.rest_api_base}/profiles",
                headers=headers,
                json=profile_data,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Error upserting profile: %s", exc)
            return False

    def save_user_profile(
        self,
        user_id: str,
        name: str,
        email: str,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o-mini",
        communication_style: str = "balanced",
        preferences: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save or update user profile in Supabase profiles table
        
        Args:
            user_id: Unique user identifier
            name: User's name
            email: User's email
            llm_provider: Preferred LLM provider
            llm_model: Preferred LLM model
            communication_style: Preferred communication style (must be one of: concise, detailed, balanced, technical, casual, formal)
            preferences: Additional user preferences
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.error("Cannot save user profile; Supabase credentials not configured")
            return False

        # Validate communication_style
        communication_style_lower = communication_style.lower() if isinstance(communication_style, str) else str(communication_style).lower()
        if communication_style_lower not in VALID_COMMUNICATION_STYLES:
            logger.error(
                "Invalid communication_style '%s'. Must be one of: %s",
                communication_style,
                ", ".join(VALID_COMMUNICATION_STYLES)
            )
            return False

        try:
            profile_data = {
                "name": name,
                "email": email,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "communication_style": communication_style_lower,
                "preferences": preferences or {},
            }

            success = self._upsert_profile(user_id, profile_data)
            if success:
                logger.info("Profile saved for user %s", user_id)
            return success

        except Exception as exc:
            logger.error("Error saving profile for user %s: %s", user_id, exc)
            return False

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Retrieve user profile from Supabase profiles table
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            UserProfile if found, None otherwise
        """
        if not self.is_configured:
            logger.error("Cannot retrieve user profile; Supabase credentials not configured")
            return None

        try:
            profile_data = self._fetch_profile(user_id)
            if not profile_data:
                return None

            # Validate and normalize communication_style from database
            comm_style = profile_data.get("communication_style", "balanced")
            if isinstance(comm_style, str):
                comm_style_lower = comm_style.lower()
                if comm_style_lower not in VALID_COMMUNICATION_STYLES:
                    logger.warning(
                        "Invalid communication_style '%s' found in database for user %s, defaulting to 'balanced'",
                        comm_style,
                        user_id
                    )
                    comm_style = "balanced"
                else:
                    comm_style = comm_style_lower
            else:
                comm_style = "balanced"

            profile: UserProfile = {
                "name": profile_data.get("name") or "User",
                "email": profile_data.get("email", ""),
                "llm_provider": profile_data.get("llm_provider", "openai"),
                "llm_model": profile_data.get("llm_model", "gpt-4o-mini"),
                "communication_style": comm_style,  # type: ignore
                "preferences": profile_data.get("preferences", {}),
                "created_at": profile_data.get("created_at", datetime.now().isoformat()),
                "updated_at": profile_data.get("updated_at", datetime.now().isoformat()),
            }

            return profile
        except Exception as exc:
            logger.error("Error retrieving profile for user %s: %s", user_id, exc)
            return None

    def update_user_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: Any,
    ) -> bool:
        """
        Update a specific user preference
        
        Args:
            user_id: Unique user identifier
            preference_key: Key of the preference to update
            preference_value: New value for the preference
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.error("Cannot update preference; Supabase credentials not configured")
            return False

        try:
            # Get existing profile
            profile_data = self._fetch_profile(user_id)
            if not profile_data:
                logger.warning("No profile found for user %s", user_id)
                return False

            # Update preferences
            preferences = profile_data.get("preferences", {})
            preferences[preference_key] = preference_value

            # Update the profile
            update_data = {"preferences": preferences}
            success = self._upsert_profile(user_id, update_data)
            
            if success:
                logger.info("Updated preference '%s' for user %s", preference_key, user_id)
            return success

        except Exception as exc:
            logger.error("Error updating preference for user %s: %s", user_id, exc)
            return False

    def update_llm_config(
        self,
        user_id: str,
        llm_provider: str,
        llm_model: str,
    ) -> bool:
        """
        Update user's LLM configuration
        
        Args:
            user_id: Unique user identifier
            llm_provider: LLM provider name
            llm_model: LLM model name
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.error("Cannot update LLM config; Supabase credentials not configured")
            return False

        try:
            # Check if profile exists, create minimal one if not
            profile_data = self._fetch_profile(user_id)
            if not profile_data:
                logger.warning(
                    "No profile found for user %s, creating minimal profile", user_id
                )
                return self.save_user_profile(
                    user_id=user_id,
                    name="Unknown",
                    email="",
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )

            # Update LLM config
            update_data = {
                "llm_provider": llm_provider,
                "llm_model": llm_model,
            }
            success = self._upsert_profile(user_id, update_data)
            
            if success:
                logger.info(
                    "Updated LLM config for user %s: %s/%s",
                    user_id,
                    llm_provider,
                    llm_model,
                )
            return success

        except Exception as exc:
            logger.error("Error updating LLM config for user %s: %s", user_id, exc)
            return False

    def save_memory(
        self,
        user_id: str,
        memory_key: str,
        memory_data: Dict[str, Any],
        namespace: Optional[tuple] = None,
    ) -> bool:
        """
        Save arbitrary memory data for a user (stored in preferences for now)
        
        Args:
            user_id: Unique user identifier
            memory_key: Key for the memory
            memory_data: Data to store
            namespace: Optional custom namespace (ignored for now)
            
        Returns:
            True if successful, False otherwise
        """
        # Store in preferences with a special prefix
        memory_key_prefixed = f"_memory_{memory_key}"
        return self.update_user_preference(user_id, memory_key_prefixed, memory_data)

    def get_memory(
        self,
        user_id: str,
        memory_key: str,
        namespace: Optional[tuple] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve memory data for a user
        
        Args:
            user_id: Unique user identifier
            memory_key: Key of the memory to retrieve
            namespace: Optional custom namespace (ignored for now)
            
        Returns:
            Memory data if found, None otherwise
        """
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return None
            
            memory_key_prefixed = f"_memory_{memory_key}"
            return profile["preferences"].get(memory_key_prefixed)
        except Exception as exc:
            logger.error("Error retrieving memory for user %s: %s", user_id, exc)
            return None

    def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        namespace: Optional[tuple] = None,
    ) -> list:
        """
        Search user memories (basic implementation using preferences)
        
        Args:
            user_id: Unique user identifier
            query: Search query
            limit: Maximum number of results
            namespace: Optional custom namespace
            
        Returns:
            List of matching memories
        """
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return []
            
            # Simple search through memory keys
            results = []
            for key, value in profile["preferences"].items():
                if key.startswith("_memory_") and query.lower() in str(value).lower():
                    results.append(value)
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as exc:
            logger.error("Error searching memories for user %s: %s", user_id, exc)
            return []


# Global service instance
_global_user_memory_service: Optional[UserMemoryService] = None


def get_user_memory_service(store: Optional[Any] = None) -> UserMemoryService:
    """
    Get UserMemoryService instance (singleton pattern)
    
    Args:
        store: Deprecated; maintained for backward compatibility.
    
    Returns:
        UserMemoryService instance
    """
    global _global_user_memory_service
    
    if _global_user_memory_service is None:
        _global_user_memory_service = UserMemoryService()
    
    return _global_user_memory_service