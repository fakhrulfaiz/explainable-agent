"""
LLM Administration Router for dynamic model switching
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, Annotated
from src.services.llm_service import LLMService, get_llm_service
from src.services.explainable_agent import ExplainableAgent
from src.services.simple_agent import SimpleAgent
from src.services.async_simple_agent import AsyncSimpleAgent
from src.services.explainable_agent_copy import ParallelExplainableAgent
from src.models.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

class LLMSwitchRequest(BaseModel):
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    groq_api_key: Optional[str] = None

class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    available_providers: list
    available_models: Dict[str, list]

@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config(
    llm_service: Annotated[LLMService, Depends(get_llm_service)]
):
  
    current_config = llm_service.get_current_config()
    available_providers = llm_service.get_available_providers()
    
    available_models = {}
    for provider in available_providers:
        available_models[provider] = llm_service.get_provider_models(provider)
    
    return LLMConfigResponse(
        provider=current_config['provider'],
        model=current_config.get('model', 'unknown'),
        available_providers=available_providers,
        available_models=available_models
    )

@router.post("/switch")
async def switch_llm(
    request: LLMSwitchRequest, 
    app_request: Request,
    llm_service: Annotated[LLMService, Depends(get_llm_service)]
):
   
    try:
        kwargs = {}
        if request.api_key:
            kwargs['api_key'] = request.api_key
        if request.base_url:
            kwargs['base_url'] = request.base_url
        if request.groq_api_key:
            kwargs['groq_api_key'] = request.groq_api_key
        
        result = llm_service.switch_llm(
            provider=request.provider,
            model=request.model,
            **kwargs
        )
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        # Update app state with new LLM
        new_llm = llm_service.get_current_llm()
        app_request.app.state.llm = new_llm
        
        # Recreate agents with new LLM
        try:
            # Import mongodb_manager to get the proper mongo_memory instance
            from src.models.database import mongodb_manager
            
            # Get MongoDB memory from the manager (same as server startup)
            mongo_memory = mongodb_manager.get_mongo_memory()
            
            # Create new agent instances
            explainable_agent = ExplainableAgent(
                llm=new_llm,
                db_path=settings.database_path,
                logs_dir=settings.logs_dir,
                mongo_memory=mongo_memory
            )
            
            app_request.app.state.explainable_agent = explainable_agent
       
            logger.info(f"Successfully updated all agents with new LLM: {request.provider} - {request.model}")
            
        except Exception as e:
            logger.error(f"Failed to recreate agents: {e}")
            # Don't fail the switch if agent recreation fails
            result['warning'] = f"LLM switched but agent recreation failed: {str(e)}"
        
        return result
        
    except Exception as e:
        logger.error(f"LLM switch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test")
async def test_current_llm(
    llm_service: Annotated[LLMService, Depends(get_llm_service)]
):
  
    try:
        llm = llm_service.get_current_llm()
        response = llm.invoke("Hello! Please respond with just 'OK' to confirm you're working.")
        
        return {
            'status': 'success',
            'response': response.content if hasattr(response, 'content') else str(response),
            'config': llm_service.get_current_config()
        }
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM test failed: {str(e)}")

@router.get("/providers")
async def get_providers(
    llm_service: Annotated[LLMService, Depends(get_llm_service)]
):
    providers = llm_service.get_available_providers()
    result = {}
    
    for provider in providers:
        result[provider] = {
            'models': llm_service.get_provider_models(provider),
            'config_keys': []
        }
        
        if provider == 'openai':
            result[provider]['config_keys'] = ['api_key']
        elif provider == 'ollama':
            result[provider]['config_keys'] = ['base_url']
        elif provider == 'deepseek':
            result[provider]['config_keys'] = ['api_key']
        elif provider == 'groq':
            result[provider]['config_keys'] = ['groq_api_key']
    
    return result

