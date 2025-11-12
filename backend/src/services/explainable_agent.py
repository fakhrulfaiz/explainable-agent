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
from pydantic import BaseModel, Field
from src.models.database import get_mongo_memory
from src.tools.custom_toolkit import CustomToolkit
from src.utils.chart_utils import get_supported_charts
from src.tools.profile_tools import get_profile_tools
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
    use_planning: bool = True  # Planning preference from API
    use_explainer: bool = True  # Whether to use explainer node
    response_type: Optional[Literal["answer", "replan", "cancel"]] = None  # Type of response from planner
    agent_type: str = "data_exploration_agent"  # Which specialized agent to use
    routing_reason: str = ""  # Why this agent was chosen
    visualizations: Optional[List[Dict[str, Any]]] = []


class ExplainableAgent:
    """Data Exploration Agent - Specialized for SQL database queries and data analysis with explanations"""
    
    def __init__(self, llm, db_path: str, logs_dir: str = None, mongo_memory=None, store=None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.sql_tools = self.toolkit.get_tools()
        
        # Create custom toolkit with LLM
        self.custom_toolkit = CustomToolkit(llm=self.llm)
        self.custom_tools = self.custom_toolkit.get_tools()
        
        # Combine tools (exclude profile tools from agent exposure)
        self.tools = self.sql_tools + self.custom_tools
        
        # Store for long-term memory
        self.store = store
        self.explainer = Explainer(llm)
        self.planner = PlannerNode(llm, self.tools)
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.mongo_memory = mongo_memory
        
        # Create handoff tools for the assistant
        self.create_handoff_tools()
        
        # Create assistant as a react agent with transfer tools and profile tools
        profile_tools = get_profile_tools()
        base_assistant_agent = create_react_agent(
            model=llm,
            tools=[self.transfer_to_data_exploration] + profile_tools,  # Add transfer_to_explainer_agent when ready
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
        
        # Store use_planning value for tools to access
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
    
    
    def create_handoff_tools(self):
        """Create handoff tools for the assistant to transfer to specialized agents"""
        
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
            
            # Extract query from messages if not in state
            query = state.get("query", "")
            if not query and "messages" in state and state["messages"]:
                # Get the first human message as the query
                for msg in state["messages"]:
                    if hasattr(msg, 'content') and hasattr(msg, '__class__') and 'HumanMessage' in str(msg.__class__):
                        query = msg.content
                        break
            
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
        
        @tool("transfer_to_general_agent", description="Transfer general questions and tasks to the general-purpose agent")
        def transfer_to_general_agent(
            state: Annotated[Dict[str, Any], InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
            task_description: str = ""
        ) -> Command:
            """Transfer to general-purpose agent"""
            
            tool_message = {
                "role": "tool",
                "content": f"Transferring to general agent: {task_description}",
                "name": "transfer_to_general_agent",
                "tool_call_id": tool_call_id,
            }
            
            # Extract query from messages if not in state
            query = state.get("query", "")
            if not query and "messages" in state and state["messages"]:
                # Get the first human message as the query
                for msg in state["messages"]:
                    if hasattr(msg, 'content') and hasattr(msg, '__class__') and 'HumanMessage' in str(msg.__class__):
                        query = msg.content
                        break
            
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
                "agent_type": "general_agent",
                "routing_reason": f"Transferred to general agent: {task_description}",
                "query": task_description,
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
                goto="general_agent_flow",
                update=update_state,
                graph=Command.PARENT,
            )
        
        self.transfer_to_general_agent = transfer_to_general_agent
        
        # Future explainer agent transfer tool:
        # @tool("transfer_to_explainer_agent", description="Transfer explanation and educational tasks")
        # def transfer_to_explainer_agent(...):
        #     return Command(goto="explainer_flow", ...)
    
    def create_graph(self):
        graph = StateGraph(ExplainableAgentState)
        
        # Add nodes
        graph.add_node("assistant", self.assistant_agent)  
        graph.add_node("data_exploration_flow", self.data_exploration_entry)  
        graph.add_node("general_agent_flow", self.general_agent_entry)
        graph.add_node("planner", self.planner_node)
        graph.add_node("agent", self.agent_node)
        graph.add_node("general_agent", self.general_agent_node)
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
        # General agent flow - goes directly to general agent, then ends
        graph.add_edge("general_agent_flow", "general_agent")
        graph.add_edge("general_agent", END)
        
        # Rest of the data exploration flow
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
        
        # Add memory checkpointer for interrupt functionality
        memory = self.mongo_memory
        # Compile with store if available
        if self.store:
            return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory, store=self.store)
        else:
            return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory)
    
    def data_exploration_entry(self, state: ExplainableAgentState):
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

        # Default fallback to data exploration
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
        """Determine whether to use explainer node based on use_explainer flag"""
        use_explainer = state.get("use_explainer", True)
        
        if use_explainer:
            return "explain"
        else:
            return "agent"  # Skip explainer and go directly back to agent
    
    def agent_node(self, state: ExplainableAgentState):
        """Agent reasoning node with improved user preference handling"""
        messages = state["messages"]
        
        # Build personalized system message
        system_message = self._build_system_message()
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Filter out previous system messages to avoid conflicts
        conversation_messages = [msg for msg in messages 
                               if not isinstance(msg, SystemMessage)]
        
        # Prepare messages for LLM
        all_messages = [SystemMessage(content=system_message)] + conversation_messages
        
        response = llm_with_tools.invoke(all_messages)
        
        return {
            "messages": messages + [response],
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0),
            "query": state.get("query", ""),
            "plan": state.get("plan", "")
        }
    
    def _build_system_message(self):
        """Build system message with user preferences at the top"""
        
        # 1. USER PREFERENCES FIRST (most important for personalization)
        user_context = self._get_user_preferences()
        
        # 2. CORE ROLE AND BEHAVIOR
        base_prompt = """You are a helpful SQL database assistant.

RESPONSE STYLE:
- Be direct and concise - answer only what is asked
- Use a clear, professional tone unless user preferences indicate otherwise
- Format data as markdown tables when showing query results
- Use code blocks with syntax highlighting for code/SQL
"""
        
        # 3. DATABASE QUERY GUIDELINES
        db_guidelines = """DATABASE OPERATIONS:

You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct sqlite query to run, then look at the results of the query and return the answer.
Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.
You have access to tools for interacting with the database.
Only use the below tools. Only use the information returned by the below tools to construct your final answer.
You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

To start you should ALWAYS look at the tables in the database to see what you can query.
Do NOT skip this step.
Then you should query the schema of the most relevant tabl
"""
        
        # 4. VISUALIZATION RULES
        viz_rules = self._get_visualization_rules()
        
        # 5. TOOL USAGE RULES
        tool_rules = """TOOL USAGE:
- ONLY call tools when necessary to answer the question
- NEVER call the same tool twice with identical arguments
- Use smart_transform_for_viz ONLY when user explicitly requests a chart/graph/visualization
- Stop and inform user if you can't find required data
"""
        
        # 6. OUTPUT FORMAT RULES
        output_rules = """OUTPUT FORMAT:
- NEVER generate base64 images (no data:image/png;base64,...)
- NEVER use markdown image tags for charts: ![chart](...)
- For visualizations: only call smart_transform_for_viz tool, don't generate images
- For user-provided image URLs from database: use markdown format ![Alt](url)
- Keep explanations brief and relevant

"""
        
        # 7. INTERACTION GUIDELINES
        interaction_rules = """INTERACTION:
- After providing data, you MAY suggest ONE relevant next step if valuable
- Example: "Would you like to visualize this as a chart?"
- Keep suggestions minimal - don't repeatedly prompt for actions
- If request is clear and complete, just answer it without extra suggestions
"""
        
        # Combine all sections with clear hierarchy
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

Bad Examples (DON'T DO):
- Generating base64 images
- Calling visualization without explicit request
- Using unsupported chart types
- Calling same tool multiple times
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
            
            # Build style-specific instructions
            style_instructions = {
                "concise": "Keep responses brief and to-the-point. Use short sentences. Avoid lengthy explanations unless specifically asked.",
                "detailed": "Provide thorough explanations with context and examples. Include relevant details that help understanding.",
                "balanced": "Provide clear explanations with moderate detail. Balance brevity with completeness.",
                "technical": "Use technical terminology freely. Include implementation details and technical context.",
                "casual": "Use a friendly, conversational tone. Feel free to use contractions and approachable language.",
                "formal": "Use professional, polite language. Avoid contractions and maintain a formal tone."
            }
            
            style_instruction = style_instructions.get(comm_style, style_instructions["balanced"])
            
            # Format preferences context
            pref_context = f"""═══════════════════════════════════════
USER PREFERENCES (PRIORITY: HIGHEST)
═══════════════════════════════════════
Name: {user_name}
Communication Style: {comm_style}

STYLE INSTRUCTIONS:
{style_instruction}
"""
            
            # Add custom preferences if they exist
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
            # Gracefully handle errors - don't break the agent
            print(f"Warning: Could not load user preferences: {e}")
            return ""
    
    def _get_visualization_rules(self):
        """Get visualization rules with supported chart types"""
        try:
            supported = get_supported_charts()
            charts_help = [
                f"  • {chart_type}: variants = {', '.join(info.get('variants', []))}"
                for chart_type, info in supported.items()
            ]
            supported_charts_list = "\n".join(charts_help)
            
            return f"""VISUALIZATION GUIDELINES:

Supported Chart Types:
{supported_charts_list}

When to Create Visualizations:
• ONLY when user explicitly asks for: chart, graph, visualization, plot
• Examples: "show a bar chart", "create a line graph", "visualize this data"
• If user asks for multiple charts, call smart_transform_for_viz separately for each

How to Create Visualizations:
• Call smart_transform_for_viz with: raw_data, columns, viz_type
• If viz_type not specified by user, choose the most appropriate based on data
• Provide brief context before the visualization
• DO NOT generate any image data yourself
"""
        except Exception:
            return """VISUALIZATION GUIDELINES:
• Use smart_transform_for_viz tool when user requests charts/graphs
• Only call when explicitly requested
• Do not generate image data
"""
    
    def general_agent_node(self, state: ExplainableAgentState):
        """General-purpose agent that can answer anything"""
        messages = state["messages"]
        
        system_message = """You are a helpful general-purpose AI assistant. You can answer questions, have conversations, provide explanations, help with various tasks, and engage in general discussion.

Guidelines:
- Be helpful, accurate, and conversational
- Provide clear and detailed explanations when asked
- If you don't know something, say so honestly
- Be friendly and engaging in your responses
- Use markdown formatting when appropriate for better readability
- If asked about specific topics, provide comprehensive and useful information"""

        # Use the LLM directly without tools for general conversation
        conversation_messages = [msg for msg in messages 
                               if not isinstance(msg, SystemMessage)]
        
        # Prepare messages for LLM
        all_messages = [SystemMessage(content=system_message)] + conversation_messages
        
        response = self.llm.invoke(all_messages)
        
        return {
            "messages": messages + [response],
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0),
            "query": state.get("query", ""),
            "plan": state.get("plan", "")
        }
    
    def tool_explanation_node(self, state: ExplainableAgentState):
        """
        Generates a brief explanation of upcoming tool calls before execution.
        """
        messages = state["messages"]
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        
        # Early return if no tool calls
        if not getattr(last_message, 'tool_calls', None):
            return {"messages": []}
        
        # Build tool name to description mapping
        tool_name_to_desc = {}
        for tool in getattr(self, 'tools', []) or []:
            name = getattr(tool, 'name', None)
            desc = getattr(tool, 'description', None)
            if name:
                tool_name_to_desc[name] = desc or "No description available"
        
        # Format tool descriptions with args
        tool_descriptions = []
        for call in last_message.tool_calls:
            name = call.get('name', 'unknown')
            args = call.get('args', {})
            desc = tool_name_to_desc.get(name, "No description available")
            
            # Format args compactly
            args_str = json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            
            tool_descriptions.append(f"- {name}: {desc}\n  Args: {args_str}")
        
        tools_text = "\n".join(tool_descriptions)
        
        # Get user preferences for personalized explanation
        user_preferences = self._get_user_preferences()
        
        # Generate explanation with full context
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
        result = tool_node.invoke({"messages": messages})
        
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

        return {
            "messages": result["messages"],
            "steps": steps,
            "step_counter": step_counter,
            "query": state.get("query", ""),
            "plan": state.get("plan", "")
        }
    
    def explainer_node(self, state: ExplainableAgentState):
        """Explain the last step taken and ensure all steps have required fields"""
        steps = state.get("steps", [])
        updated_steps = []
        
        for i, step in enumerate(steps):
            # Create a copy to avoid mutating original state
            step_copy = step.copy()
            
            # Check if step is missing required fields
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
            "plan": state.get("plan", "")
        }
    def get_interrupt_state(self, config=None):
         
        if config is None:
            config = {"configurable": {"thread_id": "main_thread"}}
        return self.graph.get_state(config)
    
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
            
            # Update custom toolkit with new LLM
            self.custom_toolkit = CustomToolkit(llm=new_llm)
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

    
