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
    
    def __init__(self, llm, db_path: str, logs_dir: str = None, mongo_memory=None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.sql_tools = self.toolkit.get_tools()
        
        # Create custom toolkit with LLM
        self.custom_toolkit = CustomToolkit(llm=self.llm)
        self.custom_tools = self.custom_toolkit.get_tools()
        
        # Combine all tools
        self.tools = self.sql_tools + self.custom_tools
        self.explainer = Explainer(llm)
        self.planner = PlannerNode(llm, self.tools)
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.mongo_memory = mongo_memory
        
        # Create handoff tools for the assistant
        self.create_handoff_tools()
        
        # Create assistant as a react agent with transfer tools
        base_assistant_agent = create_react_agent(
            model=llm,
            tools=[self.transfer_to_data_exploration, self.transfer_to_general_agent],  # Add transfer_to_explainer_agent when ready
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
                "- CRITICAL: Make only ONE tool call per user message. Pass the full task in a single call.\n"
                "- The specialized agent will handle all aspects of the request (multiple charts, queries, etc.)\n"
                "- Example: If user asks for '3 different charts', call the transfer tool ONCE with the full request\n"
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
                "tools": "tools",
                "end": END
            }
        )
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
        """Agent reasoning node"""
        messages = state["messages"]
        
        # Get tool descriptions dynamically
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
        system_message = prompt_template.format(dialect="SQLite", top_k=5)
        system_message += f"""

You are a concise SQL database assistant. Answer only what is asked, nothing more.
- If user asks what tables exist, just list the tables
- If user asks for data, return the data in markdown table format when appropriate
- ONLY use smart_transform_for_viz tool when the user EXPLICITLY asks for a chart, graph, or visualization
- If user asks for multiple charts, call smart_transform_for_viz multiple times with different viz_type parameters, strictly only use supported types.
- Supported types: bar, line, pie
- If user didn not specify a viz_type, decide the most appropriate type based on the data and context.

For pie charts, analyze the data and context to choose the most appropriate variant:
- 'simple': Basic categorical proportions (e.g., "Show product categories distribution")
- 'donut': When emphasizing totals or adding center text (e.g., "Show sales by department with total in center")
- 'two-level': For hierarchical data (e.g., "Show Yes/No responses with subcategories")
- 'straight-angle': For precise proportion comparisons (e.g., "Compare market shares precisely")

Consider these factors when choosing pie variants:
1. Data structure (hierarchical, flat, nested)
2. User's intent (comparison, exploration, overview)
3. Number of categories (too many categories might need grouping)

- Do NOT use smart_transform_for_viz for regular data queries - just return markdown tables
- Use tools only when necessary to answer the specific question
- NEVER generate images or base64 image data (no data:image/png;base64,...). Do not include markdown image tags for charts.
- For images referenced by the user (not charts) or urls from database, use markdown format: ![Alt text](image_url)
- For tabular data, format as markdown tables with proper headers and alignment
- Give explanation but be direct and brief - no unnecessary explanations or extra tool calls
- If you cant find any tables or columns, say so, stop the tool calling and provide information. Do not make up data.
- IMPORTANT: Do NOT call the same tool with same arguments multiple times. Call each tool only once per response.
- IMPORTANT: Only use smart_transform_for_viz tool when user specifically requests a visualization/chart
- IMPORTANT: Do not generate any images or base64 data for visualizations - only use the smart_transform_for_viz tool to return a JSON spec for the frontend renderer.
- If you accidentally produced an image or base64 output, remove it and instead produce a concise textual summary.
- Follow the plan strictly if one exists.

Examples (Visualization requests):

Bar Chart Example:
User: "Show a bar chart of the top 5 actors by film count"
Assistant (good):
1) Provide a one-paragraph summary of findings (no images)
2) Call smart_transform_for_viz with raw_data, columns, and viz_type='bar'
3) Just brief explanation

Pie Chart Examples:
1. Simple Pie Chart:
User: "Show me the distribution of film ratings"
Assistant (good):
1) Brief summary of rating distribution
2) Call smart_transform_for_viz with:
   - viz_type='pie'
   - config.variant='simple'


2. Two-Level Pie:
User: "Show rental status (returned/not returned) with breakdown by store"
Assistant (good):
1) Brief summary of rental status
2) Call smart_transform_for_viz with:
   - viz_type='pie'
   - config.variant='two-level'
   - Organize data into inner (status) and outer (store) rings


Bad Examples (Do NOT do):
- "![Chart](data:image/png;base64,...)"  (No base64 images)
- Calling visualization tool without explicit request
- Using unsupported chart types
"""

        # Bind tools to LLM so it can call them
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

    
