"""
Custom toolkit for the explainable agent project.
Automatically passes LLM instance to custom tools.
"""

from langchain.agents.agent_toolkits.base import BaseToolkit
from langchain.tools import BaseTool
from typing import List, Any
from pydantic import Field
from .visualization_tools import SmartTransformForVizTool


class CustomToolkit(BaseToolkit):
    """Custom toolkit that automatically passes LLM to tools"""
    
    llm: Any = Field(description="Language model instance")
    
    def __init__(self, llm: Any, **kwargs):
        super().__init__(llm=llm, **kwargs)
    
    def get_tools(self) -> List[BaseTool]:
        """Get all custom tools with LLM automatically injected"""
        return [
            SmartTransformForVizTool(llm=self.llm),
        ]