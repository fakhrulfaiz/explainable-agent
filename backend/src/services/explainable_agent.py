from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import MessagesState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.types import Command
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
import json
import os
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from src.models.database import get_mongo_memory
from src.tools.custom_toolkit import CustomToolkit
from src.utils.chart_utils import get_supported_charts
from src.tools.profile_tools import get_profile_tools
from src.models.chat_models import DataContext

logger = logging.getLogger(__name__)
try:
    from explainer import Explainer
    from nodes.planner_node import PlannerNode
except ImportError:
    from .explainer import Explainer
    from ..nodes.planner_node import PlannerNode

class ExplainableAgentState(MessagesState):
    query: str
    plan: str
    steps: List[Dict[str, Any]]
    step_counter: int
    human_comment: Optional[str]
    status: Literal["approved", "feedback", "cancelled"]
    assistant_response: str
    use_planning: bool = True  
    use_explainer: bool = True  
    response_type: Optional[Literal["answer", "replan", "cancel"]] = None  
    agent_type: str = "data_exploration_agent" 
    routing_reason: str = ""  
    visualizations: Optional[List[Dict[str, Any]]] = []
    data_context: Optional[DataContext] = None  


class ExplainableAgent:
    """Data Exploration Agent - Specialized for SQL database queries and data analysis with explanations"""
    
    def __init__(self, llm, db_path: str, logs_dir: str = None, mongo_memory=None, store=None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.sql_tools = self.toolkit.get_tools()
        self.custom_toolkit = CustomToolkit(llm=self.llm, db_engine=self.engine)
        self.custom_tools = self.custom_toolkit.get_tools()
        self.tools = self.sql_tools + self.custom_tools
        self.store = store
        self.explainer = Explainer(llm)
        self.planner = PlannerNode(llm, self.tools)
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.mongo_memory = mongo_memory
    
        self.create_handoff_tools()
        profile_tools = get_profile_tools()
        base_assistant_agent = create_react_agent(
            model=llm,
            tools=[self.transfer_to_data_exploration] + profile_tools, 
            prompt=(
                "You are an assistant that handles user preferences and routes tasks to specialized agents.\n\n"
                "AVAILABLE TOOLS:\n"
                "- Profile Tools: save_user_preference, update_user_name, update_communication_style, get_user_profile\n"
                "  Use these for: Setting nicknames, communication preferences, saving any user preferences\n"
                "- data_exploration_agent: Handles database queries and visualizations, SQL analysis, and data exploration\n"
                "  Use this for: SQL queries, database analysis, table inspection, data queries, schema questions\n\n"
                "PREFERENCE HANDLING:\n"
                "- Handle user preferences INDEPENDENTLY without transferring to other agents\n"
                "- When user says 'Call me X' or 'My name is X', use update_user_name\n"
                "- When user requests communication style changes (concise/detailed/balanced), use update_communication_style\n"
                "- For ANY other preferences (themes, notifications, custom settings, etc.), use save_user_preference\n"
                "- After updating preferences, confirm briefly and ask if there's anything else\n\n"
                "ROUTING LOGIC:\n"
                "- For PREFERENCE-ONLY queries: Handle with profile tools, respond briefly, DO NOT transfer\n"
                "- For DATA EXPLORATION queries: Transfer to data_exploration_agent\n"
                "- For MIXED queries (preferences + data): Handle preferences FIRST, then transfer the data part\n"
                "- For general conversation: Respond normally without transferring\n\n"
                "TRANSFER RULES:\n"
                "- IMPORTANT: Only route to agents when you receive a NEW user message, not for agent responses\n"
                "- **CRITICAL: ONLY USE ONE TOOL CALL PER USER MESSAGE for transfers. PASS THE FULL TASK IN A SINGLE CALL.**\n"
                "- **CRITICAL: DO NOT SAY ANYTHING WHEN TRANSFERRING. JUST TRANSFER.**\n"
                "- **Example: If user asks for '3 different charts', call the transfer tool ONCE with the full request**\n"
                "- **Example: If user asks for different objects or parameters, call the transfer tool ONCE with the full request**\n"
                "- For mixed queries, handle preferences first, then transfer only the non-preference part\n\n"
                "EXAMPLES:\n"
                "- 'Call me Sarah' → Use update_user_name, confirm, no transfer\n"
                "- 'Show me sales data' → Transfer to data_exploration_agent\n"
                "- 'Call me Alex and show me the database schema' → Use update_user_name, then transfer 'show me the database schema'\n"
            ),
            name="assistant"
        )
    
        self._use_planning = None
        self._use_explainer = None
        
        def assistant_agent(state):
            use_planning = state.get("use_planning", True)
            use_explainer = state.get("use_explainer", True)
            agent_type = state.get("agent_type", "data_exploration_agent")
            query = state.get("query", "")
            
            # Store use_planning value for tools to access
            self._use_planning = use_planning
            self._use_explainer = use_explainer
            result = base_assistant_agent.invoke(state)
            
            if isinstance(result, dict):
                result["use_planning"] = use_planning
                result["use_explainer"] = use_explainer
                result["agent_type"] = agent_type
                result["query"] = query
            
            return result
        
        self.assistant_agent = assistant_agent
        
        # Create the graph
        self.graph = self.create_graph()
    
    
    def _get_latest_human_message(self, messages: List[BaseMessage]) -> Optional[str]:
        if not messages:
            return None
        for msg in reversed(messages):
            if hasattr(msg, 'content') and hasattr(msg, '__class__') and 'HumanMessage' in str(msg.__class__):
                return msg.content
        return None
    
    def create_handoff_tools(self):
        @tool("transfer_to_data_exploration", description="Transfer database and SQL queries to the data exploration agent")
        def transfer_to_data_exploration(
            state: Annotated[Dict[str, Any], InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
            task_description: str = ""
        ) -> Command:
            """Transfer to data exploration agent"""
            
            tool_message = {
                "role": "tool",
                "content": f"Transferring to data exploration agent: {task_description}",
                "name": "transfer_to_data_exploration",
                "tool_call_id": tool_call_id,
            }
            
            # Extract query from latest human message for new queries
            # Only update if status is "approved" (new query), not "feedback" (planner_node handles it)
            query = state.get("query", "")
            status = state.get("status", "approved")
            
            if status == "approved" and "messages" in state and state["messages"]:
                latest_human_msg = self._get_latest_human_message(state["messages"])
                if latest_human_msg:
                    query = latest_human_msg
            
            # Get use_planning value from stored value
            use_planning = self._use_planning
            if use_planning is None:
                use_planning = state.get("use_planning", True)
            
            # Get use_explainer value from state
            use_explainer = self._use_explainer
            if use_explainer is None:
                use_explainer = state.get("use_explainer", True)
            
            update_state = {
                "messages": state.get("messages", []) + [tool_message],
                "agent_type": "data_exploration_agent",
                "routing_reason": f"Transferred to data exploration agent: {task_description}",
                "query": query,
                "plan": state.get("plan", ""),
                "steps": state.get("steps", []),
                "step_counter": state.get("step_counter", 0),
                "human_comment": state.get("human_comment"),
                "status": state.get("status", "approved"),
                "assistant_response": state.get("assistant_response", ""),
                "use_planning": use_planning,
                "use_explainer": use_explainer,
                "visualizations": state.get("visualizations", [])
            }
            
            
            return Command(
                goto="data_exploration_flow",
                update=update_state,
                graph=Command.PARENT,
            )
        
        self.transfer_to_data_exploration = transfer_to_data_exploration
        
    def create_graph(self):
        graph = StateGraph(ExplainableAgentState)
        
        # Add nodes
        graph.add_node("assistant", self.assistant_agent)  
        graph.add_node("data_exploration_flow", self.data_exploration_entry)
        graph.add_node("general_agent_flow", self.general_agent_entry)
        graph.add_node("planner", self.planner_node)
        graph.add_node("agent", self.agent_node)
        graph.add_node("tools", self.tools_node)
        graph.add_node("tool_explanation", self.tool_explanation_node)
        graph.add_node("explain", self.explainer_node)
        graph.add_node("human_feedback", self.human_feedback)
        
        # Start with assistant for routing
        graph.set_entry_point("assistant")
        
        # Data exploration flow entry point - decides planning vs direct
        graph.add_conditional_edges(
            "data_exploration_flow",
            self.should_plan,
            {
                "planner": "planner",
                "agent": "agent"
            }
        )

        graph.add_edge("planner", "human_feedback")
        graph.add_conditional_edges(
            "human_feedback",
            self.should_execute,
            {
                "agent": "agent",
                "planner": "planner",
                "end": END
            }
        )
        graph.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "tools": "tool_explanation",
                "end": END
            }
        )
        graph.add_edge("tool_explanation", "tools")
        graph.add_conditional_edges(
            "tools",
            self.should_explain,
            {
                "explain": "explain",
                "agent": "agent"
            }
        )
        graph.add_edge("explain", "agent")
        
        memory = self.mongo_memory
        if self.store:
            return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory, store=self.store)
        else:
            return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory)
    
    def data_exploration_entry(self, state: ExplainableAgentState):
        status = state.get("status", "approved")
        messages = state.get("messages", [])
        current_query = state.get("query", "")
        
        if status == "approved":
            latest_human_msg = self._get_latest_human_message(messages)
            if latest_human_msg and latest_human_msg != current_query:
                return {
                    **state,
                    "query": latest_human_msg
                }
        
        return state
    
    def general_agent_entry(self, state: ExplainableAgentState):
        return state
    
    
    def should_plan(self, state: ExplainableAgentState):
        agent_type = state.get("agent_type", "data_exploration_agent")
        use_planning = state.get("use_planning", True)
        
        if agent_type == "data_exploration_agent":
            if use_planning:
                return "planner"  # Go through planning first
            else:
                return "agent"    # Go directly to data exploration

        return "planner" if use_planning else "agent"
    
    def human_feedback(self, state: ExplainableAgentState):
        pass
    
    def should_execute(self, state: ExplainableAgentState):
        if state.get("status") == "approved":
            return "agent"
        elif state.get("status") == "feedback":
            return "planner"
        else:
            return "end"  # End the conversation
        
        
        
    def planner_node(self, state: ExplainableAgentState):
       
        return self.planner.execute(state)
    
    def should_continue(self, state: ExplainableAgentState):
     
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        else:
            return "end"  # End the conversation after agent completes
    
    def should_explain(self, state: ExplainableAgentState):
        use_explainer = state.get("use_explainer", True)
        
        if use_explainer:
            return "explain"
        else:
            return "agent"  # Skip explainer and go directly back to agent
    
    def agent_node(self, state: ExplainableAgentState):
        messages = state["messages"]
        
        system_message = self._build_system_message()
        
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        conversation_messages = [msg for msg in messages 
                               if not isinstance(msg, SystemMessage)]
        
        all_messages = [SystemMessage(content=system_message)] + conversation_messages
        
        response = llm_with_tools.invoke(all_messages)
        
        return {
            "messages": messages + [response],
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0),
            "query": state.get("query", ""),
            "plan": state.get("plan", ""),
            "data_context": state.get("data_context"),  
            "visualizations": state.get("visualizations", [])  
        }
    
    def _build_system_message(self):
        """Build system message with user preferences at the top"""
        
        user_context = self._get_user_preferences()
        base_prompt = """You are a helpful SQL database assistant.

CORE RESPONSIBILITIES:
1. Answer user questions accurately using the available tools.
2. Avoid making assumptions; verify with data.
3. Be efficient: Do not repeat successful tool calls.

RESPONSE STYLE:
- Be direct and concise - answer only what is asked
- Use a clear, professional tone unless user preferences indicate otherwise
- Format data as markdown tables when showing query results
- Use code blocks with syntax highlighting for code/SQL
"""
        db_guidelines = """DATABASE OPERATIONS:

1. **EXPLORATION FIRST**:
   - Always check `sql_db_list_tables` or `sql_db_schema` if you are unsure about table names or columns.
   - Do not guess column names.

2. **QUERY CONSTRUCTION**:
   - Write syntactically correct SQLite queries.
   - **LIMIT RESULTS**: Always use `LIMIT` (e.g., 5-10) if planning to user sql_db_query tool unless the user asks for all data oor something that require large data.
   - **SELECTIVE**: Select only necessary columns.
   - **READ-ONLY**: SELECT statements ONLY. No INSERT/UPDATE/DELETE.

3. **ERROR HANDLING**:
   - If a query fails, check the error message.
   - Common errors: Wrong column name, syntax error.
   - Fix the query and try ONCE more. If it fails again, ask the user for clarification.
"""

        viz_rules = self._get_visualization_rules()

        tool_rules = """TOOL USAGE & EXECUTION STRATEGY:

1. **THINK BEFORE ACTING**:
   - Before calling a tool, check the conversation history.
   - Has this tool been called with these arguments before? If yes, DO NOT call it again. Use the existing output.
   - Do you have enough information to answer? If yes, stop calling tools and answer.

2. **PREVENTING RECURSION & LOOPS**:
   - You are limited to a small number of tool calls per turn.
   - If a tool fails or returns unexpected results, DO NOT retry immediately with the same arguments.
   - Analyze the error, change your approach, or inform the user.
   - **CRITICAL**: If you find yourself calling the same tool twice with same arguments and still produce error, STOP.

3. **CHOOSING THE RIGHT TOOL**:
   - **sql_db_query**: For simple, specific questions that require 5-10 rows of data.
   - **sql_db_to_df**: For complex analysis, plotting, or large datasets. Stores data in Redis for other tools.
   - **python_repl**: For calculations/analysis on the DataFrame created by `sql_db_to_df`.
   - **large_plotting_tool**: For static images (matplotlib) or complex statistical plots.
   - **smart_transform_for_viz**: For simple, interactive frontend charts (bar, line, pie).

4. **WORKFLOWS**:
   - **Analysis**: `sql_db_to_df` -> `dataframe_info` -> `python_repl`
   - **Plotting**: `sql_db_to_df` -> `large_plotting_tool` 
   - **Simple Query**: `sql_db_query`-> `smart_transform_for_viz`(IF ASK FOR VISUALIZATION)

5. **DATAFRAME MANAGEMENT**:
   - Always check if `df` is available/expired before using `python_repl` or `large_plotting_tool`.
   - If expired/missing, run `sql_db_to_df` first.
"""

        output_rules = """OUTPUT FORMAT:
- Avoid generating base64 images directly (use appropriate visualization tools instead)
- For frontend visualizations: use smart_transform_for_viz tool rather than generating images
- For matplotlib/static plots: use large_plotting_tool (it handles image upload and returns markdown)
- For image URLs from database: use standard markdown format ![Alt](url)
- Keep explanations clear and relevant to the user's request
"""

        interaction_rules = """INTERACTION:
- After providing data, you can suggest relevant next steps when helpful
- Example: "Would you like to visualize this data or perform additional analysis?"
- Keep suggestions natural and relevant to the user's workflow
- Focus on answering the user's question completely and clearly
"""

        system_message = f"""{user_context}

{base_prompt}

{db_guidelines}

{viz_rules}

{tool_rules}

{output_rules}

{interaction_rules}

EXAMPLES:

Good Visualization Request:
User: "Show a bar chart of top 5 actors by film count"
Response:
1. Brief summary: "Here are the top 5 actors by film count..."
2. Call smart_transform_for_viz with viz_type='bar'
3. Done - no images or extra suggestions

Things to Avoid:
- Generating base64 images directly
- Creating visualizations without user request
- Using unsupported chart types
- Calling the same tool repeatedly with identical arguments
- Looping on failed queries
"""
        
        return system_message
    
    def _get_user_preferences(self):
        """Get and format user preferences"""
        try:
            from langgraph.config import get_config
            from src.services.user_memory_service import get_user_memory_service
            
            config = get_config()
            configurable = config.get("configurable", {})
            user_id = configurable.get("user_id")
            
            if not user_id:
                return ""
            
            memory_service = get_user_memory_service()
            if not getattr(memory_service, "is_configured", False):
                return ""
            
            profile = memory_service.get_user_profile(user_id)
            if not profile:
                return ""
            
            user_name = profile.get("name", "")
            comm_style = profile.get("communication_style", "balanced")
            preferences = profile.get("preferences", {})
   
            style_instructions = {
                "concise": "Keep responses brief and to-the-point. Use short sentences. Avoid lengthy explanations unless specifically asked.",
                "detailed": "Provide thorough explanations with context and examples. Include relevant details that help understanding.",
                "balanced": "Provide clear explanations with moderate detail. Balance brevity with completeness.",
                "technical": "Use technical terminology freely. Include implementation details and technical context.",
                "casual": "Use a friendly, conversational tone. Feel free to use contractions and approachable language.",
                "formal": "Use professional, polite language. Avoid contractions and maintain a formal tone."
            }
            
            style_instruction = style_instructions.get(comm_style, style_instructions["balanced"])
   
            pref_context = f"""═══════════════════════════════════════
USER PREFERENCES (PRIORITY: HIGHEST)
═══════════════════════════════════════
Name: {user_name}
Communication Style: {comm_style}

STYLE INSTRUCTIONS:
{style_instruction}
"""
  
            if preferences:
                pref_context += f"Custom Settings:\n"
                for key, value in preferences.items():
                    pref_context += f"  • {key}: {value}\n"
            
            pref_context += """
PERSONALIZATION RULES:
• Address user as "{name}" when natural and appropriate
• Strictly follow the communication style throughout your entire response
• Apply style to ALL parts: greetings, explanations, data presentation, and suggestions
• Consider custom preferences when relevant to the task

═══════════════════════════════════════
""".format(name=user_name if user_name else "the user")
            
            return pref_context
            
        except Exception as e:
            print(f"Warning: Could not load user preferences: {e}")
            return ""
    
    def _get_visualization_rules(self):
        """Get visualization rules with intelligent tool selection logic"""
        try:
            supported = get_supported_charts()
            charts_help = [
                f"  • {chart_type}: variants = {', '.join(info.get('variants', []))}"
                for chart_type, info in supported.items()
            ]
            supported_charts_list = "\n".join(charts_help)
            
            return f"""VISUALIZATION GUIDELINES:

TOOL SELECTION LOGIC:
You have TWO visualization tools available:

1. smart_transform_for_viz (Frontend Charts):
   • Use for: Simple bar, line, pie charts with ≤ 100 rows
   • Use for: Standard frontend-rendered visualizations
   • Use for: When data can be easily aggregated/summarized
   • Supported types: {supported_charts_list}

2. large_plotting_tool (Matplotlib Images):
   • Use for: Large datasets (> 100 rows) - tool handles SQL query internally
   • Use for: Complex scatter plots with many data points
   • Use for: Time series data with many points
   • Use for: Statistical plots (histograms, box plots, etc.)
   • Use for: When user specifically requests "matplotlib", "static image", or "high-quality" plots
   • Use for: Advanced matplotlib features not available in frontend charts

DECISION PROCESS:
1. First, determine if user wants a visualization (chart, graph, plot, visualize)
2. If yes, consider the data size and complexity:
   - Small/simple data (≤100 rows): Use smart_transform_for_viz
   - Large/complex data (>100 rows): Use large_plotting_tool
   - User requests "matplotlib" or "high-quality": Use large_plotting_tool
3. For large_plotting_tool: Pass SQL query directly, don't fetch data first
4. For smart_transform_for_viz: Fetch data first, then pass to tool

IMPORTANT:
• NEVER fetch large datasets (>100 rows) to pass to smart_transform_for_viz
• Let large_plotting_tool handle SQL execution for big datasets
• Choose the right tool based on data size and user requirements
• DO NOT generate any image data yourself
"""
        except Exception:
            return """VISUALIZATION GUIDELINES:
• Use smart_transform_for_viz for small datasets (≤100 rows)
• Use large_plotting_tool for large datasets (>100 rows)
• Only call when explicitly requested
• Do not generate image data
"""


    def tool_explanation_node(self, state: ExplainableAgentState):
      
        messages = state["messages"]
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        
        if not getattr(last_message, 'tool_calls', None):
            return {"messages": []}

        if getattr(last_message, 'content', None):
            return {"messages": []}

        tool_name_to_desc = {}
        for tool in getattr(self, 'tools', []) or []:
            name = getattr(tool, 'name', None)
            desc = getattr(tool, 'description', None)
            if name:
                tool_name_to_desc[name] = desc or "No description available"
        
        tool_descriptions = []
        for call in last_message.tool_calls:
            name = call.get('name', 'unknown')
            args = call.get('args', {})
            desc = tool_name_to_desc.get(name, "No description available")
            
        
            args_str = json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            
            tool_descriptions.append(f"- {name}: {desc}\n  Args: {args_str}")
        
        tools_text = "\n".join(tool_descriptions)
        

        user_preferences = self._get_user_preferences()
        

        system_prompt = f"""

Provide a concise, user-facing explanation (1–2 sentences) of the next step you will take to answer the question.

Internal context (do not expose tool names):
{tools_text}

Use a clear, professional, conversational tone. Focus on the intent and expected outcome, not too detailed on implementation details.
Do not mention specific tool names or parameters.

Examples:
- 'I'll first review the database structure to identify where this information is stored.'
- 'Now, I'll run a targeted query to retrieve the relevant records and summarize the results.'"""

        
        try:
            # Include all previous messages for context
            explanation_messages = [SystemMessage(content=system_prompt)] + messages[:-1]
            response = self.llm.invoke(explanation_messages)
            explanation_text = getattr(response, 'content', str(response))
        except Exception:
            explanation_text = f"Running the following tools:\n{tools_text}"
        
        # Modify the existing message instead of adding new one
        modified_message = AIMessage(
            content=explanation_text,
            tool_calls=getattr(last_message, 'tool_calls', None),
            id=getattr(last_message, 'id', None)
        )
        
        # Replace the last message
        return {
            "messages": messages[:-1] + [modified_message]
        }
    
    def tools_node(self, state: ExplainableAgentState):
   
        messages = state["messages"]
        last_message = messages[-1]
        
        steps = state.get("steps", [])
        step_counter = state.get("step_counter", 0)
    
        # Execute tools
        tool_node = ToolNode(tools=self.tools)
        result = tool_node.invoke(state)
        
        logger.info("Tool node result: %s", result)
        
        # Capture step information for explainer
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                step_counter += 1
                
                # Find the corresponding tool output
                tool_output = None
                for msg in result["messages"]:
                    if hasattr(msg, 'tool_call_id') and msg.tool_call_id == tool_call['id']:
                        tool_output = msg.content
                        break
                
                step_info = {
                    "id": step_counter,
                    "type": tool_call['name'],
                    "tool_name": tool_call['name'],
                    "input": json.dumps(tool_call['args']),
                    "output": tool_output or "No output captured",
                    "context": state.get("query", "Database query"),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add explanation fields with default values when explainer is disabled
                use_explainer = state.get("use_explainer", True)
                if not use_explainer:
                    step_info.update({
                        "decision": f"Execute {tool_call['name']} tool",
                        "reasoning": f"Used {tool_call['name']} to process the query",
                        "confidence": 0.8,
                        "why_chosen": f"Selected {tool_call['name']} as the appropriate tool"
                    })
                
                steps.append(step_info)
                
                if tool_call['name'] == "smart_transform_for_viz":
                    try:
                        viz_dict = json.loads(tool_output)
                        state["visualizations"].append(viz_dict)
                    except json.JSONDecodeError:
                        print(f"Failed to parse visualization output: {tool_output}")
                        state["visualizations"].append({"error": "Invalid JSON output"})

                if tool_call['name'] == "sql_db_to_df":
                    logger.info(
                        "sql_db_to_df raw output for tool_call_id=%s: %s",
                        tool_call.get('id'),
                        tool_output,
                    )
                    try:
                        parsed_output = json.loads(tool_output)
                    except (TypeError, json.JSONDecodeError):
                        logger.info(
                            "Failed to parse sql_db_to_df output for tool_call_id=%s. Raw output: %s",
                            tool_call.get('id'),
                            tool_output,
                        )
                        continue
                    
                    data_context_payload = parsed_output.get("data_context")
                    if data_context_payload:
                        try:
                            # Convert shape list to tuple if needed
                            if "shape" in data_context_payload and isinstance(data_context_payload["shape"], list):
                                data_context_payload["shape"] = tuple(data_context_payload["shape"])
                            
                            # Parse datetime strings if needed
                            if "created_at" in data_context_payload and isinstance(data_context_payload["created_at"], str):
                                data_context_payload["created_at"] = datetime.fromisoformat(data_context_payload["created_at"])
                            
                            if "expires_at" in data_context_payload and isinstance(data_context_payload["expires_at"], str):
                                data_context_payload["expires_at"] = datetime.fromisoformat(data_context_payload["expires_at"])
                            
                            state["data_context"] = DataContext(**data_context_payload)
                            logger.info(
                                "Successfully updated data_context for tool_call_id=%s: df_id=%s",
                                tool_call.get('id'),
                                data_context_payload.get('df_id')
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to create DataContext for tool_call_id=%s. Error: %s. Payload: %s",
                                tool_call.get('id'),
                                str(e),
                                data_context_payload,
                                exc_info=True
                            )
                    

        return {
            "messages": result["messages"],
            "steps": steps,
            "step_counter": step_counter,
            "query": state.get("query", ""),
            "plan": state.get("plan", ""),
            "data_context": state.get("data_context"),  # Preserve DataFrame context
            "visualizations": state.get("visualizations", [])  # Preserve visualizations
        }
    
    def explainer_node(self, state: ExplainableAgentState):
        """Explain the last step taken and ensure all steps have required fields"""
        steps = state.get("steps", [])
        updated_steps = []
        
        for i, step in enumerate(steps):
            step_copy = step.copy()
            
            missing_fields = [field for field in ["decision", "reasoning", "confidence", "why_chosen"] 
                             if field not in step_copy]
            
            if missing_fields:
                try:
                    if i == len(steps) - 1:
                        # Get detailed explanation for the last step
                        explanation = self.explainer.explain_step(step_copy)
                        step_copy.update({
                            "decision": explanation.decision,
                            "reasoning": explanation.reasoning,
                            "why_chosen": explanation.why_chosen,
                            "confidence": explanation.confidence
                        })
                    else:
                        # For previous steps, try to generate better defaults based on available data
                        tool_type = step_copy.get('type', 'unknown')
                        tool_result = step_copy.get('result', 'No result available')
                        
                        step_copy.update({
                            "decision": f"Execute {tool_type} tool",
                            "reasoning": f"Used {tool_type} to process the query. Result: {str(tool_result)[:100]}...",
                            "confidence": 0.7,  # Lower confidence for auto-generated explanations
                            "why_chosen": f"Selected {tool_type} as the appropriate tool for this step"
                        })
                except Exception as e:
                    # Fallback if explanation generation fails
                    step_copy.update({
                        "decision": f"Step {i+1} execution",
                        "reasoning": f"Error generating explanation: {str(e)}",
                        "confidence": 0.5,
                        "why_chosen": "Unable to determine reasoning"
                    })
            
            updated_steps.append(step_copy)
        
        return {
            "messages": state["messages"],
            "steps": updated_steps,
            "step_counter": state.get("step_counter", 0),
            "query": state.get("query", ""),
            "plan": state.get("plan", ""),
            "data_context": state.get("data_context"),  # Preserve DataFrame context
            "visualizations": state.get("visualizations", [])  # Preserve visualizations
        }
    
    def continue_with_feedback(self, user_feedback: str, status: str = "feedback", config=None):

        if config is None:
            config = {"configurable": {"thread_id": "main_thread"}}
        
        state_update = {"human_comment": user_feedback, "status": status}
        self.graph.update_state(config, state_update)
        
        events = list(self.graph.stream(None, config, stream_mode="values"))
        return events
    
    def approve_and_continue(self, config=None):
     
        if config is None:
            config = {"configurable": {"thread_id": "main_thread"}}
        state_update = {"status": "approved"}
        self.graph.update_state(config, state_update)
        
        # Continue execution
        events = list(self.graph.stream(None, config, stream_mode="values"))
        return events

    def update_llm(self, new_llm):
        """Update the LLM for this agent and all its components"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Log if using Ollama
        if hasattr(new_llm, 'model') and 'ollama' in str(type(new_llm)).lower():
            logger.info("Using Ollama LLM - no special fallbacks applied")
        
        try:
            # Update the main LLM
            self.llm = new_llm
            
            # Update toolkit with new LLM
            self.toolkit = SQLDatabaseToolkit(db=self.db, llm=new_llm)
            self.sql_tools = self.toolkit.get_tools()
            
            # Update custom toolkit with new LLM and database engine
            self.custom_toolkit = CustomToolkit(llm=new_llm, db_engine=self.engine)
            self.custom_tools = self.custom_toolkit.get_tools()
            
            # Update combined tools
            self.tools = self.sql_tools + self.custom_tools
            
            # Update explainer with new LLM
            self.explainer = Explainer(new_llm)
            
            # Update planner with new LLM and tools
            self.planner = PlannerNode(new_llm, self.tools)
            
            # Recreate the assistant agent with new LLM
            base_assistant_agent = create_react_agent(
                model=new_llm,
                tools=[self.transfer_to_data_exploration, self.transfer_to_general_agent],
                prompt=(
                    "You are an assistant that routes tasks to specialized agents.\n\n"
                    "AVAILABLE AGENTS:\n"
                    "- data_exploration_agent: Handles database queries, SQL analysis, and data exploration\n"
                    "  Use this for: SQL queries, database analysis, table inspection, data queries, schema questions\n\n"
                    "- general_agent: Handles general questions, conversations, and any other tasks\n"
                    "  Use this for: general questions, conversations, explanations, help, or anything not database-related\n\n"
                    "FUTURE AGENTS (planned):\n"
                    "- explainer_agent: Explains concepts, processes, code, or any topic to users\n"
                    "  Will be used for: explanations, tutorials, concept clarification, how-to questions\n\n"
                    "INSTRUCTIONS:\n"
                    "- Analyze the user's request and determine which specialized agent should handle it\n"
                    "- For database/SQL related queries, use transfer_to_data_exploration\n"
                    "- For general questions, conversations, or anything else, use transfer_to_general_agent\n"
                    "- Be helpful and direct in your routing decisions\n"
                    "- IMPORTANT: Only route to agents when you receive a NEW user message, not for agent responses\n"
                ),
                name="assistant"
            )
            
            # Update the assistant agent function
            def assistant_agent(state):
                use_planning = state.get("use_planning", True)
                use_explainer = state.get("use_explainer", True)
                agent_type = state.get("agent_type", "data_exploration_agent")
                query = state.get("query", "")
                
                # Store use_planning value for tools to access
                self._use_planning = use_planning
                self._use_explainer = use_explainer
                result = base_assistant_agent.invoke(state)
                
                if isinstance(result, dict):
                    result["use_planning"] = use_planning
                    result["use_explainer"] = use_explainer
                    result["agent_type"] = agent_type
                    result["query"] = query
                
                return result
            
            self.assistant_agent = assistant_agent
            
            # Recreate the graph with updated components
            self.graph = self.create_graph()
            
            return True
            
        except Exception as e:
            return False

    
