from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import sys
from typing import Annotated
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from datetime import datetime
from contextlib import asynccontextmanager
from langchain_deepseek import ChatDeepSeek
# Import your project modules
from src.models.config import settings
from src.models.schemas import QueryRequest, QueryResponse
from src.services.explainable_agent import ExplainableAgent

from routers import graph, test_stream, chat_history, explorer, llm, streaming_graph, visualization
from src.models.database import mongodb_manager, get_mongodb
from routers.chat_history import get_chat_history_service
from src.middleware.auth import get_current_user, get_optional_user
from src.models.supabase_user import SupabaseUser


def setup_logging():
    
    import os
    os.makedirs(settings.logs_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Console handler for Docker logs
            logging.StreamHandler(sys.stdout),
            # File handler for persistent logs
            logging.FileHandler(
                os.path.join(settings.logs_dir, 'application.log'),
                encoding='utf-8'
            )
        ]
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger("src.services.chat_history_service").setLevel(logging.INFO)
    logging.getLogger("src.services.checkpoint_service").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce noise
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configuration complete")
    return logger


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize resources
    logger = setup_logging()
    logger.info("Starting up Explainable Agent API...")
    
    # Configure LangSmith tracing if enabled
    if settings.langsmith_tracing and settings.langsmith_api_key:
        import os
        os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        logger.info(f"✅ LangSmith tracing enabled for project: {settings.langsmith_project}")
    else:
        logger.info("⚠️  LangSmith tracing disabled (set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to enable)")
    
    # Initialize LLM using service for dynamic switching
    from src.services.llm_service import get_llm_service
    llm_service = get_llm_service()
    llm = llm_service.get_current_llm()
    logger.info(f"✅ Using LLM: {llm_service.get_current_config()}")

    # Initialize Store for long-term memory
    from langgraph.store.memory import InMemoryStore
    from src.services.user_memory_service import get_user_memory_service
    
    # Use InMemoryStore for development (use PostgresSaver for production)
    store = InMemoryStore()
    user_memory_service = get_user_memory_service(store=store)
    logger.info("✅ Long-term memory store initialized")

    # Initialize MessageManagementService
    from src.repositories.dependencies import get_message_management_service, get_messages_repository, get_chat_thread_repository
    from pymongo.database import Database
    
    # Get database instance
    db = mongodb_manager.get_database()
    
    # Create agent instances (message service will be injected via dependency injection)
    explainable_agent = ExplainableAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir,
        mongo_memory=mongodb_manager.get_mongo_memory(),
        store=store  # Pass store for long-term memory
    )
    
    app.state.llm = llm
    app.state.llm_service = llm_service
    app.state.explainable_agent = explainable_agent
    app.state.store = store
    app.state.user_memory_service = user_memory_service
  
    logger.info("All services initialized successfully!")
    
    yield
    
    logger.info("Shutting down Explainable Agent API...")
    # Close MongoDB connections
    mongodb_manager.close()
    


# Create FastAPI instance with lifespan
app = FastAPI(
    title=settings.app_name,
    description="API for the Explainable Agent system",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

# Configure CORS with settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Include routers
app.include_router(graph.router)
app.include_router(streaming_graph.router)
app.include_router(test_stream.router)
app.include_router(chat_history.router)
app.include_router(explorer.router)
app.include_router(visualization.router)

# Include LLM router  
from routers import llm
app.include_router(llm.router)

# Authentication endpoints
@app.get("/api/auth/me")
async def get_current_user_info(current_user: SupabaseUser = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user.model_dump()

@app.get("/api/auth/status")
async def get_auth_status(request: Request, user: SupabaseUser = Depends(get_optional_user)):
    """Check authentication status (optional)"""
    return {
        "authenticated": user is not None,
        "user": user.model_dump() if user else None
    }

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Explainable Agent API is running"}

# Dependency functions that access app state
def get_llm(request: Request):
    return request.app.state.llm

def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

# Routes with Dependency Injection
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}




if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
