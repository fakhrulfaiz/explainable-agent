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
    
    # Agent routing information
    agent_type: str = "data_exploration_agent"  # Which specialized agent to use
    routing_reason: str = ""  # Why this agent was chosen


class ExplainableAgent:
    """Data Exploration Agent - Specialized for SQL database queries and data analysis with explanations"""
    
    def __init__(self, llm, db_path: str, logs_dir: str = None, mongo_memory=None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.tools = self.toolkit.get_tools()
        self.explainer = Explainer(llm)
        self.planner = PlannerNode(llm, self.tools)
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.mongo_memory = mongo_memory
        
        # Create handoff tools for the assistant
        self.create_handoff_tools()
        
        # Create assistant as a react agent with transfer tools
        self.assistant_agent = create_react_agent(
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
            ),
            name="assistant"
        )
        
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
            
            # Ensure all required fields are present with defaults
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
                "use_planning": state.get("use_planning", True)
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
            
            # Ensure all required fields are present with defaults
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
                "use_planning": state.get("use_planning", True)
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
        graph.add_edge("tools", "explain")
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
        
        # Currently only data_exploration_agent is implemented
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
- Use tools only when necessary to answer the specific question
- For images, use markdown format: ![Alt text](image_url)
- For tabular data, format as markdown tables with proper headers and alignment
- Give explaination but be direct and brief - no unnecessary explanations or extra tool calls
- Follow the plan strictly if one exists."""

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
                
                steps.append(step_info)
        
        return {
            "messages": result["messages"],
            "steps": steps,
            "step_counter": step_counter,
            "query": state.get("query", ""),
            "plan": state.get("plan", "")
        }
    
    def explainer_node(self, state: ExplainableAgentState):
        """Explain the last step taken"""
        steps = state.get("steps", [])
        
        if steps:
            # Get the last step
            last_step = steps[-1]
            
            # Get explanation from explainer
            explanation = self.explainer.explain_step(last_step)
            
            # Update the step with explanation (now using Pydantic model)
            last_step.update({
                "decision": explanation.decision,
                "reasoning": explanation.reasoning,
                "why_chosen": explanation.why_chosen,
                "confidence": explanation.confidence
            })
        
        return {
            "messages": state["messages"],
            "steps": steps,
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

    def process_query(self, user_query: str):
        """Process a user query using the explainable agent with explanations"""
        try:
            start_time = datetime.now()
            
            initial_state = ExplainableAgentState(
                messages=[HumanMessage(content=user_query)],
                query=user_query,
                plan="",  # Will be filled by planner node
                steps=[],
                step_counter=0,
                status="approved",  # Default to approved for initial run
                assistant_response="",
                use_planning=True,  # Default to planning enabled
                agent_type="data_exploration_agent",  # Default agent type
                routing_reason=""  # Will be filled by assistant node
            )
            
         
            config = {"configurable": {"thread_id": "main_thread"}}
            events = list(self.graph.stream(initial_state, config, stream_mode="values"))
            
            # Check if we hit an interrupt
            current_state = self.graph.get_state(config)
            if current_state.next:  # If there are pending nodes, we hit an interrupt
                # Get the current state for display
                state_values = current_state.values
                
                return {
                    "success": True,
                    "interrupted": True,
                    "plan": state_values.get("plan", ""),
                    "state": current_state,
                    "config": config,
                    "message": "Execution interrupted for human feedback. Use approve_and_continue() or continue_with_feedback() to proceed."
                }
            
            # Get final state
            final_state = events[-1] if events else initial_state
            steps = final_state.get("steps", [])
            
            # Extract final answer
            final_answer = ""
            if events and "messages" in events[-1]:
                for msg in reversed(events[-1]["messages"]):
                    if (hasattr(msg, 'content') and msg.content and 
                        type(msg).__name__ == 'AIMessage' and
                        (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                        final_answer = msg.content
                        break
            
            # Get final explanation
            final_explanation = self.explainer.explain_final_result(
                steps, final_answer, user_query
            )
            
            # Add final result step
            if final_answer:
                final_step = {
                    "id": len(steps) + 1,
                    "type": "final_result",
                    "decision": "Generated final structured answer",
                    "reasoning": "Synthesized all previous steps into a comprehensive final answer",
                    "input": "All previous step results and agent final message",
                    "output": json.dumps(final_explanation.model_dump(), indent=2),
                    "confidence": final_explanation.confidence,
                    "why_chosen": "Required for structured output format",
                    "timestamp": datetime.now().isoformat()
                }
                steps.append(final_step)
            
            # Calculate total time
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # Calculate overall confidence
            confidences = [step.get("confidence", 0.8) for step in steps if "confidence" in step]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.8
            
            # Get the plan from final state
            final_plan = final_state.get("plan", "No plan available")
            
            # Create structured log
            structured_log = {
                "question": user_query,
                "plan": final_plan,
                "steps": steps,
                "final_structured_result": final_explanation.model_dump(),
                "total_time": total_time,
                "overall_confidence": overall_confidence
            }
            
            # Save log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.logs_dir, f"explainable_agent_interaction_{timestamp}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(structured_log, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "response": final_answer if final_answer else "No clear response generated",
                "structured_log": structured_log,
                "log_file": log_file,
                "events": events
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
