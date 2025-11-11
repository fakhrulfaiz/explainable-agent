"""
Profile Management Tools - Tools that the agent can use to manage user profiles
"""
from langchain_core.tools import tool
from typing import Optional, Dict, Any
from dataclasses import dataclass
from src.services.user_memory_service import get_user_memory_service
from langgraph.config import get_config
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Context for user identification"""
    user_id: str


@tool
def save_user_preference(
    preference_key: str,
    preference_value: Any
) -> str:
    """
    Save a user preference to their profile. 
    Use this when the user tells you about their preferences, likes, dislikes, or settings.
    
    Examples:
    - User says "I prefer concise answers" -> save_user_preference("communication_style", "concise")
    - User says "I like technical details" -> save_user_preference("technical_level", "expert")
    - User says "I'm a beginner" -> save_user_preference("technical_level", "beginner")
    """
    try:
        # Get user_id from config
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
        except Exception:
            user_id = None
        
        if not user_id:
            return "Error: User ID not found. User must be authenticated to save preferences."
        
        memory_service = get_user_memory_service()
        success = memory_service.update_user_preference(
            user_id=user_id,
            preference_key=preference_key,
            preference_value=preference_value
        )
        
        if success:
            return f"Successfully saved preference '{preference_key}': {preference_value}"
        else:
            return f"Failed to save preference '{preference_key}'"
            
    except Exception as e:
        logger.error(f"Error saving user preference: {e}")
        return f"Error saving preference: {str(e)}"


@tool
def update_user_name(
    name: str
) -> str:
    """
    Update the user's name in their profile.
    Use this when the user tells you their name or asks you to remember their name.
    
    Example:
    - User says "My name is John" -> update_user_name("John")
    - User says "Call me Sarah" -> update_user_name("Sarah")
    """
    try:
        # Get user_id from config
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
        except Exception:
            user_id = None
        
        if not user_id:
            return "Error: User ID not found. User must be authenticated."
        
        memory_service = get_user_memory_service()
        if not getattr(memory_service, "is_configured", False):
            return SUPABASE_CONFIG_ERROR
        
        # Get existing profile
        profile = memory_service.get_user_profile(user_id)
        email = profile.get("email", "") if profile else ""
        
        # Update name by saving full profile
        success = memory_service.save_user_profile(
            user_id=user_id,
            name=name,
            email=email,
            llm_provider=profile.get("llm_provider", "openai") if profile else "openai",
            llm_model=profile.get("llm_model", "gpt-4o-mini") if profile else "gpt-4o-mini",
            communication_style=profile.get("communication_style", "balanced") if profile else "balanced",
            preferences=profile.get("preferences", {}) if profile else {}
        )
        
        if success:
            return f"Successfully updated name to: {name}"
        else:
            return "Failed to update name"
            
    except Exception as e:
        logger.error(f"Error updating user name: {e}")
        return f"Error updating name: {str(e)}"


@tool
def update_communication_style(
    style: str
) -> str:
    """
    Update the user's preferred communication style.
    Use this when the user tells you how they want you to communicate.
    
    Valid styles: "concise", "detailed", "balanced", "technical", "casual", "formal"
    
    Examples:
    - User says "Be more concise" -> update_communication_style("concise")
    - User says "Give me more details" -> update_communication_style("detailed")
    - User says "Keep it balanced" -> update_communication_style("balanced")
    - User says "Be more technical" -> update_communication_style("technical")
    - User says "Be casual" -> update_communication_style("casual")
    - User says "Be formal" -> update_communication_style("formal")
    """
    try:
        # Get user_id from config
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
        except Exception:
            user_id = None
        
        if not user_id:
            return "Error: User ID not found. User must be authenticated."
        
        # Validate style - import from user_memory_service for consistency
        try:
            from src.services.user_memory_service import VALID_COMMUNICATION_STYLES
        except ImportError:
            VALID_COMMUNICATION_STYLES = ["concise", "detailed", "balanced", "technical", "casual", "formal"]
        
        if style.lower() not in VALID_COMMUNICATION_STYLES:
            return f"Invalid style. Must be one of: {', '.join(VALID_COMMUNICATION_STYLES)}"
        
        memory_service = get_user_memory_service()
        
        # Get existing profile
        profile = memory_service.get_user_profile(user_id)
        
        # Update by saving full profile
        success = memory_service.save_user_profile(
            user_id=user_id,
            name=profile.get("name", "User") if profile else "User",
            email=profile.get("email", "") if profile else "",
            llm_provider=profile.get("llm_provider", "openai") if profile else "openai",
            llm_model=profile.get("llm_model", "gpt-4o-mini") if profile else "gpt-4o-mini",
            communication_style=style.lower(),
            preferences=profile.get("preferences", {}) if profile else {}
        )
        
        if success:
            return f"Successfully updated communication style to: {style}"
        else:
            return "Failed to update communication style"
            
    except Exception as e:
        logger.error(f"Error updating communication style: {e}")
        return f"Error updating communication style: {str(e)}"


@tool
def update_llm_preference(
    provider: str,
    model: str
) -> str:
    """
    Update the user's preferred LLM provider and model.
    Use this when the user explicitly asks to change the AI model or provider.
    
    Valid providers: "openai", "ollama", "deepseek", "groq"
    
    Examples:
    - User says "Use GPT-4" -> update_llm_preference("openai", "gpt-4o")
    - User says "Switch to Ollama" -> update_llm_preference("ollama", "llama3.1:8b")
    """
    try:
        # Get user_id from config
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
        except Exception:
            user_id = None
        
        if not user_id:
            return "Error: User ID not found. User must be authenticated."
        
        # Validate provider
        valid_providers = ["openai", "ollama", "deepseek", "groq"]
        if provider.lower() not in valid_providers:
            return f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        
        memory_service = get_user_memory_service()
        success = memory_service.update_llm_config(
            user_id=user_id,
            llm_provider=provider.lower(),
            llm_model=model
        )
        
        if success:
            return f"Successfully updated LLM preference to {provider}/{model}. This will be used in future conversations."
        else:
            return "Failed to update LLM preference"
            
    except Exception as e:
        logger.error(f"Error updating LLM preference: {e}")
        return f"Error updating LLM preference: {str(e)}"


@tool
def get_user_profile() -> str:
    """
    Get the current user's profile information.
    Use this to check what preferences and settings the user has.
    This helps you personalize your responses based on their stored preferences.
    """
    try:
        # Get user_id from config
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
        except Exception:
            user_id = None
        
        if not user_id:
            return "Error: User ID not found. User must be authenticated."
        
        memory_service = get_user_memory_service()
        if not getattr(memory_service, "is_configured", False):
            return SUPABASE_CONFIG_ERROR
        
        profile = memory_service.get_user_profile(user_id)
        
        if profile:
            return f"""User Profile:
- Name: {profile.get('name', 'Not set')}
- Email: {profile.get('email', 'Not set')}
- LLM Provider: {profile.get('llm_provider', 'openai')}
- LLM Model: {profile.get('llm_model', 'gpt-4o-mini')}
- Communication Style: {profile.get('communication_style', 'balanced')}
- Preferences: {profile.get('preferences', {})}"""
        else:
            return "No profile found. User preferences will be created as they share information."
            
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return f"Error retrieving profile: {str(e)}"


@tool
def debug_profile_system() -> str:
    """
    Debug the profile system to identify configuration issues.
    Use this to troubleshoot profile-related errors.
    """
    try:
        debug_info = []
        
        # Check user_id
        try:
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
            debug_info.append(f"✅ User ID: {user_id[:8]}..." if user_id else "❌ User ID: Not found")
        except Exception as e:
            debug_info.append(f"❌ Config Error: {str(e)}")
            user_id = None
        
        # Check Supabase configuration
        memory_service = get_user_memory_service()
        is_configured = getattr(memory_service, "is_configured", False)
        debug_info.append(f"✅ Supabase Config: OK" if is_configured else "❌ Supabase Config: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        
        if user_id and is_configured:
            # Test profile retrieval
            try:
                profile = memory_service.get_user_profile(user_id)
                if profile:
                    debug_info.append(f"✅ Profile: Found (Name: {profile.get('name', 'Not set')})")
                else:
                    debug_info.append("⚠️ Profile: Not found (will be created on first save)")
            except Exception as e:
                debug_info.append(f"❌ Profile Retrieval Error: {str(e)}")
        
        return "Profile System Debug:\n" + "\n".join(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug_profile_system: {e}")
        return f"Debug Error: {str(e)}"


def get_profile_tools():
    """Get all profile management tools"""
    return [
        save_user_preference,
        update_user_name,
        update_communication_style,
        get_user_profile,
        debug_profile_system
    ]

