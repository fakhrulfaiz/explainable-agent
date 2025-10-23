from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import MessagesState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.types import Command
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
import operator
import json
import os
from datetime import datetime
from pydantic import BaseModel, Field
from src.models.database import get_mongo_memory
from src.tools.custom_toolkit import CustomToolkit
from src.utils.chart_utils import get_supported_charts
try:
    from explainer import Explainer
    from nodes.planner_node import PlannerNode
except ImportError:
    from .explainer import Explainer
    from ..nodes.planner_node import PlannerNode

class ExplainableAgentState(MessagesState):
    query: str
    plan: str
    steps: List[Dict[str, Any]] = []  # Historical steps (no operator.add - we manage manually)
    temp_steps: Annotated[List[Dict[str, Any]], operator.add] = []  # Temporary for current batch
    step_counter: int
    human_comment: Optional[str]
    status: Literal["approved", "feedback", "cancelled"]
    assistant_response: str
    use_planning: bool = True
    use_explainer: bool = True
    response_type: Optional[Literal["answer", "replan", "cancel"]] = None
    agent_type: str = "data_exploration_agent"
    routing_reason: str = ""
    visualizations: Annotated[List[Dict[str, Any]], operator.add] = []

# Separate state for individual tool execution (Map step)
class ToolExecutionState(TypedDict):
    tool_call: Dict[str, Any]
    step_id: int
    query: str


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
            tools=[self.transfer_to_data_exploration],  # Add transfer_to_explainer_agent when ready
            prompt=(
                "You are an assistant that routes tasks to specialized agents.\n\n"
                "AVAILABLE AGENTS:\n"
                "- data_exploration_agent: Handles database queries and visualizations, SQL analysis, and data exploration\n"
                "  Use this for: SQL queries, database analysis, table inspection, data queries, schema questions\n\n"
                "FUTURE AGENTS (planned):\n"
                "- explainer_agent: Explains concepts, processes, code, or any topic to users\n"
                "  Will be used for: explanations, tutorials, concept clarification, how-to questions\n\n"
                "INSTRUCTIONS:\n"
                "- Analyze the user's request and determine which specialized agent should handle it\n"
                "- For database/SQL related queries and visualizations, use transfer_to_data_exploration\n"
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
    
        # Future explainer agent transfer tool:
        # @tool("transfer_to_explainer_agent", description="Transfer explanation and educational tasks")
        # def transfer_to_explainer_agent(...):
        #     return Command(goto="explainer_flow", ...)
    
    def create_graph(self):
        graph = StateGraph(ExplainableAgentState)
        
        # Add nodes
        graph.add_node("assistant", self.assistant_agent)  
        graph.add_node("data_exploration_flow", self.data_exploration_entry)  
        graph.add_node("planner", self.planner_node)
        graph.add_node("agent", self.agent_node)
        # graph.add_node("tools", self.tools_node)
        graph.add_node("explain", self.explainer_node)
        graph.add_node("human_feedback", self.human_feedback)
        graph.add_node("execute_single_tool", self.execute_single_tool)  # Parallel tool execution
        
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
        self.route_to_parallel_tools,  # NEW: Routes to parallel execution
        ["execute_single_tool", "__end__"] 
        )
        graph.add_edge("execute_single_tool", "explain")

        graph.add_edge("explain", "agent")
        
        # Add memory checkpointer for interrupt functionality
        memory = self.mongo_memory
        return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory)
    
    def data_exploration_entry(self, state: ExplainableAgentState):
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
        
        # Check if this is a new agent iteration (after explainer completed)
        # Look for pattern: last message is AIMessage with tool_calls, but we have steps from previous iteration
        current_steps = state.get("steps", [])
        is_new_iteration = (len(current_steps) > 0 and 
                           messages and 
                           len([msg for msg in messages if hasattr(msg, 'tool_call_id')]) > 0)
        
        if is_new_iteration:
            print(f"🔄 Agent: Detected new iteration, clearing {len(current_steps)} accumulated steps")
        else:
            print(f"🔄 Agent: Continuing current iteration with {len(current_steps)} steps")
        
        # Get tool descriptions dynamically
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
        system_message = prompt_template.format(dialect="SQLite", top_k=5)
        # Add supported visualization types and variants to guide the LLM
        try:
            supported = get_supported_charts()
            charts_help = [
                f"- {chart_type}: variants = {', '.join(info.get('variants', []))}"
                for chart_type, info in supported.items()
            ]
            supported_charts = "\nSUPPORTED VISUALIZATIONS:\n" + "\n".join(charts_help) + "\n"
        except Exception:
            # Non-fatal if utils are unavailable
            pass
        system_message += f"""


You are a concise SQL database assistant. Answer only what is asked, nothing more.
- If user asks what tables exist, just list the tables
- If user asks for data, return the data in markdown table format when appropriate
- ONLY use smart_transform_for_viz tool when the user EXPLICITLY asks for a chart, graph, or visualization
- The result of smart_transform_for_viz will be used to generate the visualization in frontend, so no need to generate the chart in the response.
- If user asks for multiple charts, call smart_transform_for_viz multiple times with different viz_type parameters, strictly only use supported types.
- Supported types: {supported_charts}
- If user did not specify a viz_type, decide the most appropriate type based on the data and context.

- Do NOT use smart_transform_for_viz for regular data queries - just return markdown tables
- Use tools only when necessary to answer the specific question
- NEVER generate images or base64 image data (no data:image/png;base64,...). Do not include markdown image tags for charts.
- For images referenced by the user (not charts) or urls from database, use markdown format: ![Alt text](image_url)
- For tabular data, format as markdown tables with proper headers and alignment
- For code, format as markdown code blocks with proper syntax highlighting
- Give explanation but be direct and brief - no unnecessary explanations or extra tool calls
- If you can't find any tables or columns, say so, stop the tool calling and provide information. Do not make up data.
- You can ask follow-up questions to clarify ambiguous requests or missing information.
- After providing requested data, you MAY briefly suggest ONE relevant next step if it adds clear value (e.g., "Would you like to visualize this data as a chart?"), but keep it minimal and unobtrusive.
- Do NOT repeatedly prompt for next actions or suggest multiple follow-ups.
- If the user's request is clear and complete, just answer it directly without suggestions.
- IMPORTANT: Do NOT call the same tool with same arguments multiple times. Call each tool only once per response.
- IMPORTANT: Only use smart_transform_for_viz tool when user specifically requests a visualization/chart
- IMPORTANT: Do not generate any images or base64 data for visualizations - only use the smart_transform_for_viz tool to return a JSON spec for the frontend renderer.
- If you accidentally produced an image or base64 output, remove it and instead produce a concise textual summary.
- Follow the plan strictly if one exists.

Examples (Visualization requests):
Example:
User: "Show a bar chart of the top 5 actors by film count"
Assistant (good):
1) Provide a one-paragraph summary of findings (no images)
2) Call smart_transform_for_viz with raw_data, columns, and viz_type='bar'
3) Just brief explanation

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
        
        # Update step counter if we have tool calls
        new_step_counter = state.get("step_counter", 0)
        if hasattr(response, 'tool_calls') and response.tool_calls:
            new_step_counter += 1
        
        return {
            "messages": messages + [response],
             "steps": state.get("steps", []),  # Preserve accumulated steps across iterations
            "step_counter": new_step_counter,  # Increment counter when creating tool calls
            "query": state.get("query", ""),
            "plan": state.get("plan", "")
        }
    
    def route_to_parallel_tools(self, state: ExplainableAgentState):
        """
        Clean Map-Reduce: Routes tool calls to parallel execution using Send with minimal state
        Following the investment advisor pattern for clean separation of concerns
        """
        from langgraph.types import Send
        
        messages = state["messages"]
        last_message = messages[-1]
        
        # Check if there are tool calls
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            print("✅ No tool calls - ending conversation")
            return "__end__"
        
        tool_calls = last_message.tool_calls
        print(f"🚀 Routing {len(tool_calls)} tools for parallel execution (clean map-reduce)")
        
        # Use the current step counter (already incremented in agent_node)
        current_step = state.get("step_counter", 0)
        
        # Create Send for each tool with minimal, focused state
        sends = []
        for tool_call in tool_calls:
            # Minimal state for individual tool execution
            tool_execution_state = {
                "tool_call": tool_call,
                "step_id": current_step,  # Shared step ID for all tools in this batch
                "query": state.get("query", "")
            }
            sends.append(Send("execute_single_tool", tool_execution_state))
        
        return sends

    def execute_single_tool(self, state: ToolExecutionState):
  
        
        tool_call = state["tool_call"]
        step_id = state["step_id"]
        
        print(f"🔧 [{step_id}] Executing: {tool_call['name']}")
        
        try:
            # Find and execute the tool
            tool = next((t for t in self.tools if t.name == tool_call['name']), None)
            if not tool:
                raise ValueError(f"Tool {tool_call['name']} not found")
            
            tool_output = tool.invoke(tool_call['args'])
            
            # Create ToolMessage for the agent to see
            tool_message = ToolMessage(
                content=str(tool_output),
                tool_call_id=tool_call['id'],
                name=tool_call['name']
            )
            
            # Create step info for this individual tool execution
            step_info = {
                "id": step_id,
                "type": tool_call['name'],
                "input": json.dumps(tool_call['args']),
                "output": str(tool_output),
                "timestamp": datetime.now().isoformat(),
                "tool_call_id": tool_call['id']
            }
            
            # Handle visualization
            visualization_result = []
            if tool_call['name'] == "smart_transform_for_viz":
                try:
                    visualization = json.loads(str(tool_output))
                    visualization_result = [visualization]
                except json.JSONDecodeError:
                    print(f"Failed to parse visualization output: {tool_output}")
                    visualization_result = [{"error": "Invalid JSON output"}]
            
            print(f"✅ [{step_id}] Completed: {tool_call['name']}")
            
            # Return in format for operator.add accumulation
            result = {
                "messages": [tool_message],  # Agent will see this!
                "temp_steps": [step_info],  # Will be accumulated by operator.add
            }
            
            if visualization_result:
                result["visualizations"] = visualization_result
            
            return result
            
        except Exception as e:
            print(f"❌ [{step_id}] Error in {tool_call['name']}: {str(e)}")
            
            # Create error ToolMessage for the agent to see
            error_tool_message = ToolMessage(
                content=f"Error: {str(e)}",
                tool_call_id=tool_call['id'],
                name=tool_call['name']
            )
            
            error_step_info = {
                "id": step_id,
                "type": tool_call['name'],
                "input": json.dumps(tool_call.get('args', {})),
                "output": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "tool_call_id": tool_call['id']
            }
            
            # Return error in format for operator.add accumulation
            return {
                "messages": [error_tool_message],  # Agent will see the error!
                "temp_steps": [error_step_info]
            }

    def explainer_node(self, state: ExplainableAgentState):
        # Get the temporary steps from current batch
        latest_steps = state.get("temp_steps", [])
        
        if not latest_steps:
            return {
                "messages": state["messages"],
                "steps": state.get("steps", []),  # Keep existing steps
                "temp_steps": [],  # Clear temp
                "step_counter": state.get("step_counter", 0),
                "query": state.get("query", ""),
                "plan": state.get("plan", "")
            }
        
        current_step_id = state.get("step_counter", 0)
        latest_step_id = current_step_id if current_step_id else max(step.get("id", 0) for step in latest_steps)
        
        # Keep only the latest batch steps for combination
        latest_steps = [s for s in latest_steps if s.get("id", latest_step_id) == latest_step_id]
        
        # Group and combine parallel steps with same tool
        tool_groups = {}
        for step in latest_steps:
            tool_key = step.get("type") or "unknown"
            tool_groups.setdefault(tool_key, []).append(step)
        
        combined_steps = []
        for tool_key, group in tool_groups.items():
            if len(group) == 1:
                combined_steps.append(group[0])
            else:
                first = group[0]
                combined_steps.append({
                    "id": first.get("id", latest_step_id),
                    "type": first.get("type", tool_key),
                    "input": "; ".join(step.get("input", "{}") for step in group),
                    "output": "; ".join(step.get("output", "") for step in group),
                    "timestamp": first.get("timestamp", ""),
                    "tool_call_id": first.get("tool_call_id"),
                    "execution_count": len(group)
                })
        
        # Add explanations or defaults
        use_explainer = state.get("use_explainer", True)
        updated_latest_steps = []
        
        for i, step in enumerate(combined_steps):
            step_copy = step.copy()
            tool_type = step_copy.get('type', 'tool')
            
            needs_explanation = any(
                field not in step_copy 
                for field in ["decision", "reasoning", "confidence", "why_chosen"]
            )
            
            if needs_explanation:
                if use_explainer and i == len(combined_steps) - 1:
                    try:
                        explanation = self.explainer.explain_step(step_copy)
                        step_copy.update({
                            "decision": explanation.decision,
                            "reasoning": explanation.reasoning,
                            "why_chosen": explanation.why_chosen,
                            "confidence": explanation.confidence
                        })
                    except Exception as e:
                        step_copy.update({
                            "decision": f"Step {i + 1} execution",
                            "reasoning": f"Error generating explanation: {str(e)}",
                            "confidence": 0.5,
                            "why_chosen": "Unable to determine reasoning"
                        })
                else:
                    confidence = 0.7 if use_explainer else 1.0
                    step_copy.update({
                        "decision": f"Execute {tool_type} tool",
                        "reasoning": f"Used {tool_type} as part of agent execution",
                        "confidence": confidence,
                        "why_chosen": f"Selected {tool_type} as appropriate tool"
                    })
            
            updated_latest_steps.append(step_copy)
        
        # Append combined steps to historical steps, but replace any entries with the same id (dedupe updates)
        previous_steps = [s for s in state.get("steps", []) if s.get("id") != latest_step_id]
        all_steps = previous_steps + updated_latest_steps
        
        return {
            "messages": state["messages"],
            "steps": all_steps,  # Historical steps with new combined batch added
            "temp_steps": [],  
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

    
