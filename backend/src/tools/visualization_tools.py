"""
Visualization tools for the explainable agent project.
These tools help transform database query results into visualization-ready formats.
"""

from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict, Any, Tuple, Optional
from pydantic import Field
import json
from src.utils.pie_chart_utils import get_pie_guidance
from src.utils.bar_chart_utils import get_bar_guidance
from src.utils.line_chart_utils import get_line_guidance
from src.utils.chart_utils import get_chart_template



VIZ_FORMAT_SCHEMAS = {
    "bar": {
        "description": "Bar chart for comparing categorical data",
        "format": get_chart_template("bar", {"variant": "vertical"}),
    },
    "line": {
        "description": "Line chart for time series or trends",
        "format": get_chart_template("line", {"variant": "line"}),
    },
    "pie": {
        "description": "Pie chart for showing proportions with multiple variants",
        "format": get_chart_template("pie", {"variant": "simple"}),
    },
}

def get_pie_specific_guidance() -> str:
    return get_pie_guidance()

def get_viz_format_for_prompt(viz_type: str, config: Optional[Dict[str, Any]] = None) -> str:
    """
    Dynamically fetch visualization format schema and type-specific guidance for the prompt.
    
    Args:
        viz_type: Visualization type to include in prompt
        config: Optional configuration dict (e.g., {"variant": "donut"})
        
    Returns:
        Formatted string with schema and guidance
    """
    if viz_type not in VIZ_FORMAT_SCHEMAS:
        return ""
        
    schema = VIZ_FORMAT_SCHEMAS[viz_type]
    # Build dynamic format based on config/variant when provided
    dynamic_format = get_chart_template(viz_type, config)
    format_str = f"""
**{viz_type.upper()} Chart**
Description: {schema['description']}
Format:
```json
{json.dumps(dynamic_format, indent=2)}
```
"""
    
    # Add type-specific guidance
    if viz_type == 'pie':
        format_str += "\n" + get_pie_specific_guidance()
    elif viz_type == 'bar':
        format_str += "\n" + get_bar_guidance()
    elif viz_type == 'line':
        format_str += "\n" + get_line_guidance()
    
    return format_str


class SmartTransformForVizTool(BaseTool):
    """
    Tool that uses LLM to intelligently transform database query results into visualization format.
    Dynamically fetches appropriate format schemas based on allowed visualization types.
    """
    
    name: str = "smart_transform_for_viz"
    description: str = """ONLY use when user explicitly requests a chart, graph, or visualization.
    Transforms database query results into visualization format for frontend rendering.
    
    Parameters:
    - raw_data (list of tuples): The data to visualize
    - columns (list of strings): Column names for the data
    - context (optional string): Context about the visualization
    - viz_type (optional string): Type of visualization (bar, line, pie)
    - config (optional dict): Override specific visualization settings
    
    Returns visualization-ready JSON with chart type and formatted data.
    DO NOT use for regular data queries - use only when user asks for visualizations.
    Supported types: bar, line, pie"""
    
    llm: Any = Field(description="Language model instance for intelligent transformation")
    
    def _run(
        self,
        raw_data: List[Tuple] = None,
        columns: List[str] = None,
        context: str = "data_analysis",
        viz_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Execute the smart transform tool.
        
        Args:
            raw_data: List of data tuples
            columns: List of column names
            context: Context string for visualization
            viz_type: Type of visualization (bar, line, pie)
            config: Optional configuration overrides for the visualization
        """
        try:
            # Validate required parameters
            if raw_data is None:
                return json.dumps({"error": "raw_data is required"})
            if columns is None:
                return json.dumps({"error": "columns is required"})
            
            # Default to a single chart type if not specified
            if viz_type is None:
                viz_type = 'bar'
            
            # Convert to dict format for LLM processing
            data_dicts = [dict(zip(columns, row)) for row in raw_data]
            
            # Get format and guidance for visualization with selected variant (from config)
            viz_formats = get_viz_format_for_prompt(viz_type, config)
            
            # Use type-specific prompt
            base_prompt = """You are a data visualization expert working with an explainable AI agent. 
            Given database query results from SQL queries, transform them into the best visualization format.
            
            Your role is to help users understand their data through clear, meaningful visualizations.
            
            Guidelines:
            1. Map actual column names from the data to the visualization format
            2. Use meaningful field names that reflect the actual data structure
            3. Handle data aggregation appropriately (sum, count, average)
            4. Consider data types and relationships
            5. Prioritize clarity and interpretability
            
            CRITICAL: The field names in your output should match the actual column names from the input data.
            Do NOT use generic names like "label", "value1", "value2". Use the actual column names provided.
            
            Available Visualization Type: {viz_type}
            
            {viz_formats}
            
            IMPORTANT: Return ONLY valid JSON matching the format above. No explanations, just JSON.
            Use the format that best represents the data structure and user intent.
            Map the actual column names to the visualization format fields."""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", base_prompt),
                ("user", """Context: {context}
                
Columns: {columns}

Sample data (first 5 rows):
{sample_data}

Total rows: {total_rows}

Config: {config}

Transform this data into the most appropriate visualization format.""")
            ])
            
            # Invoke LLM with dynamic format context
            response = self.llm.invoke(
                prompt.format_messages(
                    viz_type=viz_type,
                    viz_formats=viz_formats,
                    context=context,
                    columns=columns,
                    sample_data=json.dumps(data_dicts[:5], indent=2),
                    total_rows=len(data_dicts),
                    config=json.dumps(config, indent=2) if config else "None"
                )
            )
            
            # Parse LLM response
            try:
                # Extract JSON from response (handles cases where LLM adds text)
                content = response.content.strip()
                
                # Try to find JSON in markdown code blocks
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                
                viz_config = json.loads(content)
                
                # Validate that returned type matches the requested type
                if viz_config.get("type") != viz_type:
                    raise ValueError(f"LLM returned invalid viz type: {viz_config.get('type')}, expected: {viz_type}")
                
                # Apply any provided configuration overrides
                if config and isinstance(config, dict):
                    if "config" not in viz_config:
                        viz_config["config"] = {}
                    viz_config["config"].update(config)
                    
            except (json.JSONDecodeError, ValueError) as e:
                # Fallback to basic bar chart if parsing fails
                print(f"Error parsing LLM response: {e}")
                # Use actual column names in fallback
                x_key = columns[0] if columns else "category"
                y_key = columns[1] if len(columns) > 1 else "value"
                
                viz_config = {
                    "type": "bar",
                    "title": f"Data Analysis Results ({len(data_dicts)} rows)",
                    "data": [
                        {
                            x_key: str(row[0]) if row else "N/A", 
                            y_key: row[1] if len(row) > 1 else 1
                        } 
                        for row in raw_data[:10]
                    ],
                    "config": {
                        "xAxis": {"key": x_key, "label": x_key.title()},
                        "yAxis": [{"key": y_key, "label": y_key.title()}]
                    }
                }
            
            # Add metadata
            viz_config["metadata"] = {
                "source": "smart_transform_for_viz",
                "total_rows": len(raw_data),
                "columns": columns,
                "context": context
            }
            
            return json.dumps(viz_config, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Failed to transform data: {str(e)}"})
    
    async def _arun(
        self,
        raw_data: List[Tuple] = None,
        columns: List[str] = None,
        context: str = "data_analysis",
        viz_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Async version of the tool."""
        return self._run(raw_data, columns, context, viz_type, config)