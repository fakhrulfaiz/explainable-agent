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

from routers import graph, test_stream, chat_history, explorer, llm, streaming_graph
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

    # Create agent instances
    explainable_agent = ExplainableAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir,
        mongo_memory=mongodb_manager.get_mongo_memory()
    )
    
    app.state.llm = llm
    app.state.llm_service = llm_service
    app.state.explainable_agent = explainable_agent
  
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

@app.get("/test-logs")
async def test_logs():
    """Test endpoint to verify logging is working"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Test log message - INFO level")
    logger.warning("Test log message - WARNING level")
    logger.error("Test log message - ERROR level")
    
    # Also test service loggers
    chat_logger = logging.getLogger("src.services.chat_history_service")
    checkpoint_logger = logging.getLogger("src.services.checkpoint_service")
    
    chat_logger.info("Chat service test log")
    checkpoint_logger.info("Checkpoint service test log")
    
    return {"message": "Test logs sent - check your docker logs!"}

@app.get("/debug/thread/{thread_id}")
async def debug_thread(thread_id: str, chat_service = Depends(get_chat_history_service)):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check if thread exists
        thread = await chat_service.get_thread(thread_id)
        
        if thread:
            logger.info(f"DEBUG: Thread {thread_id} exists in database")
            return {
                "exists": True,
                "thread_id": thread.thread_id,
                "title": thread.title,
                "message_count": len(thread.messages),
                "created_at": thread.created_at,
                "updated_at": thread.updated_at
            }
        else:
            logger.info(f"DEBUG: Thread {thread_id} not found in database")
            return {"exists": False, "thread_id": thread_id}
            
    except Exception as e:
        logger.error(f"DEBUG: Error checking thread {thread_id}: {e}")
        return {"error": str(e), "thread_id": thread_id}

@app.get("/debug/checkpoints/{thread_id}")
async def debug_checkpoints(thread_id: str, db = Depends(get_mongodb)):
    """Debug endpoint to check checkpoint data for a thread"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Access checkpoint collections with dots in their names within explainable_agent_db
        checkpoint_writes_collection = db["checkpointing_db.checkpoint_writes"]
        checkpoints_collection = db["checkpointing_db.checkpoints"]
        
        # Check checkpoint writes
        writes = list(checkpoint_writes_collection.find({"thread_id": thread_id}))
        logger.info(f"DEBUG: Found {len(writes)} checkpoint writes for thread {thread_id}")
        
        # Check checkpoints
        checkpoints = list(checkpoints_collection.find({"thread_id": thread_id}))
        logger.info(f"DEBUG: Found {len(checkpoints)} checkpoints for thread {thread_id}")
        
        # Convert ObjectId to string for JSON serialization
        for write in writes:
            write["_id"] = str(write["_id"])
        for checkpoint in checkpoints:
            checkpoint["_id"] = str(checkpoint["_id"])
        
        return {
            "thread_id": thread_id,
            "checkpoint_writes": {
                "count": len(writes),
                "data": writes[:5]  # Show first 5 for debugging
            },
            "checkpoints": {
                "count": len(checkpoints),
                "data": checkpoints[:5]  # Show first 5 for debugging
            }
        }
        
    except Exception as e:
        logger.error(f"DEBUG: Error checking checkpoint data for thread {thread_id}: {e}")
        return {"error": str(e), "thread_id": thread_id}


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
