from fastapi import APIRouter, Depends, Request
from typing import Annotated
from datetime import datetime

from src.models.schemas import QueryRequest, QueryResponse
from src.services.explainable_agent import ExplainableAgent
from src.services.simple_agent import SimpleAgent
from src.services.async_simple_agent import AsyncSimpleAgent

router = APIRouter(
    prefix="/agent",
    tags=["agent"]
)

# Dependency functions that access app state
def get_explainable_agent(request: Request) -> ExplainableAgent:
    return request.app.state.explainable_agent

def get_simple_agent(request: Request) -> SimpleAgent:
    return request.app.state.simple_agent

def get_async_simple_agent(request: Request) -> AsyncSimpleAgent:
    return request.app.state.async_simple_agent

@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    agent: Annotated[ExplainableAgent, Depends(get_explainable_agent)]
):
    try:
        result = {"query": request.query, "processed": True}
        
        return QueryResponse(
            success=True,
            data=result,
            message="Query processed successfully",
            timestamp=datetime.now()
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            message=f"Error processing query: {str(e)}",
            timestamp=datetime.now()
        )

@router.post("/simple-query", response_model=QueryResponse)
async def process_simple_query(
    request: QueryRequest,
    agent: Annotated[SimpleAgent, Depends(get_simple_agent)]
):
    try:
        result = agent.process_query(request.query)
        
        return QueryResponse(
            success=True,
            data=result,
            message="Simple query processed successfully" if result["success"] else f"Error: {result.get('error', 'Unknown error')}",
            timestamp=datetime.now()
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            message=f"Error processing simple query: {str(e)}",
            timestamp=datetime.now()
        )

@router.post("/async-query", response_model=QueryResponse)
async def process_async_query(
    request: QueryRequest,
    agent: Annotated[AsyncSimpleAgent, Depends(get_async_simple_agent)]
):
    try:
        result = await agent.process_query_async(request.query)
        
        return QueryResponse(
            success=result["success"],
            data={k: v for k, v in result.items() if k != "success"},
            message="Async query processed successfully" if result["success"] else f"Error: {result.get('error', 'Unknown error')}",
            timestamp=datetime.now()
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            message=f"Error processing async query: {str(e)}",
            timestamp=datetime.now()
        )
