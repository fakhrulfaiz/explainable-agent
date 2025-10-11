"""
Dynamic LLM Factory for runtime model switching
"""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from src.models.config import settings
import logging

logger = logging.getLogger(__name__)

class LLMFactory:
    
    _instance = None
    _current_llm = None
    _current_config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMFactory, cls).__new__(cls)
        return cls._instance
    
    def get_current_llm(self):
        if self._current_llm is None:
            # Initialize with default settings
            self._current_llm = self.create_llm(
                provider=settings.llm_provider,
                model=getattr(settings, f"{settings.llm_provider}_model", None)
            )
        return self._current_llm
    
    def create_llm(self, provider: str, model: str = None, **kwargs):
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
    
    def switch_llm(self, provider: str, model: str = None, **kwargs):
        """Switch to a different LLM provider/model at runtime"""
        try:
            new_llm = self.create_llm(provider, model, **kwargs)
            
            # Test the new LLM with a simple query
            test_response = new_llm.invoke("Hello")
            
            # If successful, update current LLM
            self._current_llm = new_llm
            self._current_config = {
                'provider': provider,
                'model': model,
                'kwargs': kwargs
            }
            
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
        """Get available models for a specific provider"""
        models = {
            'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            'ollama': ['llama3.1:8b', 'llama3.1:70b', 'codellama:7b', 'mistral:7b'],
            'deepseek': ['deepseek-chat', 'deepseek-coder'],
            'groq': ['llama3-8b-8192', 'llama3-70b-8192', 'mixtral-8x7b-32768']
        }
        return models.get(provider.lower(), [])

# Global factory instance
llm_factory = LLMFactory()
