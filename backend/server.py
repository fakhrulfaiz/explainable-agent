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
from src.services.explainable_agent_copy import ParallelExplainableAgent
from src.services.simple_agent import SimpleAgent
from src.services.async_simple_agent import AsyncSimpleAgent

from routers import agent, graph, test_stream, chat_history, explorer
from src.models.database import mongodb_manager, get_mongodb
from routers.chat_history import get_chat_history_service


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
    
    # Create LLM instance
    if settings.llm_provider.lower() == "ollama":
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        logger.info(f"✅ Using Ollama model: {settings.ollama_model} at {settings.ollama_base_url}")
    else:
        llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        logger.info(f"LLM Provider: {settings.llm_provider}")
        logger.info(f"✅ Using OpenAI model: {settings.openai_model}")

    deepseek_llm = ChatDeepSeek(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
    )

    # Create agent instances
    explainable_agent = ExplainableAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir,
        mongo_memory=mongodb_manager.get_mongo_memory()
    )
    
    simple_agent = SimpleAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir
    )
    
    async_simple_agent = AsyncSimpleAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir
    )
    
    parallel_agent = ParallelExplainableAgent(
        llm=llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir,
        mongo_memory=mongodb_manager.get_mongo_memory()
    )
    
    app.state.llm = llm
    app.state.explainable_agent = explainable_agent
    app.state.simple_agent = simple_agent
    app.state.async_simple_agent = async_simple_agent
    app.state.parallel_agent = parallel_agent
    
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
app.include_router(agent.router)
app.include_router(graph.router)
app.include_router(test_stream.router)
app.include_router(chat_history.router)
app.include_router(explorer.router)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Explainable Agent API is running"}

# Dependency functions that access app state
def get_llm(request: Request):
    return request.app.state.llm

def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

def get_simple_agent(request: Request) -> SimpleAgent:
    return request.app.state.simple_agent

def get_async_simple_agent(request: Request) -> AsyncSimpleAgent:
    return request.app.state.async_simple_agent

def get_parallel_agent(request: Request) -> ParallelExplainableAgent:
    return request.app.state.parallel_agent

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
