from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Annotated
from langchain_openai import ChatOpenAI
from datetime import datetime
from contextlib import asynccontextmanager
from langchain_deepseek import ChatDeepSeek
# Import your project modules
from src.models.config import settings
from src.models.schemas import QueryRequest, QueryResponse
from src.services.explainable_agent import ExplainableAgent
from src.services.simple_agent import SimpleAgent
from src.services.async_simple_agent import AsyncSimpleAgent

from routers import agent, graph, test_stream


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize resources
    print("🚀 Starting up Explainable Agent API...")
    
    # Configure LangSmith tracing if enabled
    if settings.langsmith_tracing and settings.langsmith_api_key:
        import os
        os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        print(f"✅ LangSmith tracing enabled for project: {settings.langsmith_project}")
    else:
        print("⚠️  LangSmith tracing disabled (set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to enable)")
    
    # Create LLM instance
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    deepseek_llm = ChatDeepSeek(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
    )

    # Create agent instances
    explainable_agent = ExplainableAgent(
        llm=deepseek_llm,
        db_path=settings.database_path,
        logs_dir=settings.logs_dir
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
    
    app.state.llm = llm
    app.state.explainable_agent = explainable_agent
    app.state.simple_agent = simple_agent
    app.state.async_simple_agent = async_simple_agent
    
    print("✅ All services initialized successfully!")
    
    yield
    
    print("🛑 Shutting down Explainable Agent API...")
    # Add any cleanup code here if needed
    print("✅ Cleanup completed!")


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

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Explainable Agent API is running"}

# Dependency functions that access app state
def get_llm(request: Request) -> ChatOpenAI:
    return request.app.state.llm

def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

def get_simple_agent(request: Request) -> SimpleAgent:
    return request.app.state.simple_agent

def get_async_simple_agent(request: Request) -> AsyncSimpleAgent:
    return request.app.state.async_simple_agent

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
