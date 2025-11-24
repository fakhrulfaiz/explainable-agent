"""
Custom toolkit for the explainable agent project.
Automatically passes LLM instance and database engine to custom tools.
"""

from langchain.agents.agent_toolkits.base import BaseToolkit
from langchain.tools import BaseTool
from typing import List, Any, Optional
from pydantic import Field
from .visualization_tools import SmartTransformForVizTool, LargePlottingTool


class CustomToolkit(BaseToolkit):
    """Custom toolkit that automatically passes LLM and database engine to tools"""
    
    llm: Any = Field(description="Language model instance")
    db_engine: Optional[Any] = Field(default=None, description="Database engine for SQL execution")
    
    def __init__(self, llm: Any, db_engine: Any = None, **kwargs):
        super().__init__(llm=llm, db_engine=db_engine, **kwargs)
    
    def get_tools(self) -> List[BaseTool]:
        """Get all custom tools with LLM and database engine automatically injected"""
        tools = [
            SmartTransformForVizTool(llm=self.llm),
        ]
        
        # Add LargePlottingTool only if database engine is available
        if self.db_engine is not None:
            tools.append(LargePlottingTool(llm=self.llm, db_engine=self.db_engine))
        
        return tools