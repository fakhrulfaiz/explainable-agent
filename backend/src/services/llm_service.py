"""
LLM Service for runtime model switching and management
"""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from src.models.config import settings
import logging
import gc

logger = logging.getLogger(__name__)

class LLMService:
 
    
    def __init__(self):
        self._current_llm = None
        self._current_config = None
    
    def get_current_llm(self):
        if self._current_llm is None:
            self._current_llm = self.create_llm(
                provider=settings.llm_provider,
                model=getattr(settings, f"{settings.llm_provider}_model", None)
            )
        return self._current_llm
    
    def create_llm(self, provider: str, model: str = None, **kwargs):
        """Create an LLM instance for the specified provider and model"""
        provider = provider.lower()
        
        try:
            if provider == "openai":
                llm = ChatOpenAI(
                    api_key=kwargs.get('api_key') or settings.openai_api_key,
                    model=model or settings.openai_model,
                    **{k: v for k, v in kwargs.items() if k != 'api_key'}
                )
                
            elif provider == "ollama":
                llm = ChatOllama(
                    base_url=kwargs.get('base_url') or settings.ollama_base_url,
                    model=model or settings.ollama_model,
                    **{k: v for k, v in kwargs.items() if k != 'base_url'}
                )
                
            elif provider == "deepseek":
                llm = ChatDeepSeek(
                    api_key=kwargs.get('api_key') or settings.deepseek_api_key,
                    model=model or settings.deepseek_model,
                    **{k: v for k, v in kwargs.items() if k != 'api_key'}
                )
                
            elif provider == "groq":
                llm = ChatGroq(
                    api_key=kwargs.get('groq_api_key') or getattr(settings, 'groq_api_key', ''),
                    model=model or getattr(settings, 'groq_model', 'llama3-8b-8192'),
                    **{k: v for k, v in kwargs.items() if k != 'groq_api_key'}
                )
                
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            logger.info(f"✅ Created {provider} LLM with model: {model}")
            return llm
            
        except Exception as e:
            logger.error(f"❌ Failed to create {provider} LLM: {e}")
            raise
    
    def _cleanup_llm(self, llm_instance):
        """Properly cleanup old LLM instance"""
        if llm_instance is None:
            return
            
        try:
            # Close any open connections if the LLM has them
            if hasattr(llm_instance, 'close'):
                llm_instance.close()
            
            # Clear any cached data
            if hasattr(llm_instance, 'clear_cache'):
                llm_instance.clear_cache()
                
            # Delete the instance and force garbage collection
            del llm_instance
            gc.collect()
            
            logger.debug("🧹 Old LLM instance cleaned up successfully")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to cleanup old LLM instance: {e}")

    def switch_llm(self, provider: str, model: str = None, **kwargs):
        """Switch to a different LLM provider/model at runtime with proper cleanup"""
        old_llm = self._current_llm
        
        try:
            logger.info(f"🔄 Switching LLM to {provider} - {model}")
            
            # Create new LLM instance
            new_llm = self.create_llm(provider, model, **kwargs)
            
            # Test the new LLM with a simple query
            test_response = new_llm.invoke("Hello")
            logger.debug(f"✅ LLM test successful")
            
            # Cleanup old LLM before setting new one
            if old_llm is not None:
                self._cleanup_llm(old_llm)
            
            # If successful, update current LLM
            self._current_llm = new_llm
            self._current_config = {
                'provider': provider,
                'model': model,
                'kwargs': kwargs
            }
            
            logger.info(f"🎉 Successfully switched to {provider} - {model}")
            return {
                'status': 'success',
                'provider': provider,
                'model': model,
                'message': f'Successfully switched to {provider} - {model}'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to switch to {provider} - {model}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_current_config(self):
        """Get current LLM configuration"""
        if self._current_config is None:
            return {
                'provider': settings.llm_provider,
                'model': getattr(settings, f"{settings.llm_provider}_model", "unknown")
            }
        return self._current_config
    
    def get_available_providers(self):
        """Get list of available LLM providers"""
        return ['openai', 'ollama', 'deepseek', 'groq']
    
    def get_provider_models(self, provider: str):
 
        models = {
            'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
            'ollama': ['qwen2.5:latest', 'mistral:latest'],
            'deepseek': ['deepseek-chat', 'deepseek-coder'],
            'groq': ['llama3-8b-8192', 'llama3-70b-8192', 'mixtral-8x7b-32768']
        }
        return models.get(provider.lower(), [])

# Global service instance
_global_llm_service = None

# Create a function to get LLM service instance (dependency injection)
def get_llm_service() -> LLMService:
    """Get LLM service instance for dependency injection"""
    global _global_llm_service
    
    # Use singleton pattern for consistency
    if _global_llm_service is None:
        _global_llm_service = LLMService()
    
    return _global_llm_service