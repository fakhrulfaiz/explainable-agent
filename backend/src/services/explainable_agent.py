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
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
import json
import os
from datetime import datetime
from pydantic import BaseModel, Field

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


class ExplainableAgent:
    """SQL Agent with integrated explainer functionality"""
    
    def __init__(self, llm, db_path: str, logs_dir: str = None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.tools = self.toolkit.get_tools()
        
        # Initialize explainer and planner node
        self.explainer = Explainer(llm)
        self.planner = PlannerNode(llm, self.tools)
        
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Create the graph
        self.graph = self.create_graph()
    
    def create_graph(self):
        graph = StateGraph(ExplainableAgentState)
        
        # Add nodes
        graph.add_node("planner", self.planner_node)
        graph.add_node("agent", self.agent_node)
        graph.add_node("tools", self.tools_node)
        graph.add_node("explain", self.explainer_node)
        graph.add_node("human_feedback", self.human_feedback)
        
        # Add edges
        graph.set_entry_point("planner")
        
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
        memory = MemorySaver()
        return graph.compile(interrupt_before=["human_feedback"], checkpointer=memory)
    
    def human_feedback(self, state: ExplainableAgentState):
        pass
    
    def should_execute(self, state: ExplainableAgentState):
        if state.get("status") == "approved":
            return "agent"
        elif state.get("status") == "feedback":
            return "planner"
        else:
            return "end"
        
        
        
    def planner_node(self, state: ExplainableAgentState):
        """Delegate to the PlannerNode class"""
        return self.planner.execute(state)
    
    def should_continue(self, state: ExplainableAgentState):
     
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        else:
            return "end"
    
    def agent_node(self, state: ExplainableAgentState):
        """Agent reasoning node"""
        messages = state["messages"]
        
        # Get tool descriptions dynamically
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
        system_message = prompt_template.format(dialect="SQLite", top_k=5)
        system_message += f"""

You are a helpful SQL database assistant. Use the available SQL tools to answer questions about the database.

When you need to answer questions about the database, always use the appropriate tools to query the database first.
For example, to count tables, use sql_db_list_tables first to see what tables exist.
Always provide explanations for your queries and results."""

        # Bind tools to LLM so it can call them
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Prepare messages for LLM
        all_messages = [SystemMessage(content=system_message)] + messages
        
        response = llm_with_tools.invoke(all_messages)
        
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
        """Continue execution after human feedback"""
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
                status="approved"  # Default to approved for initial run
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


if __name__ == "__main__":
    # Test the explainable agent
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Check if API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set your OPENAI_API_KEY environment variable")
        exit(1)
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=api_key
    )
    
    # Database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "resource", "art.db")
    
    # Create explainable agent
    agent = ExplainableAgent(llm=llm, db_path=db_path)
    
    # Test query
    query = "Show 3 rows from the paintings table"
    print(f"Query: {query}")
    print("Processing...")
    
    result = agent.process_query(query)
    
    if result["success"]:
        print(f"\nResponse: {result['response']}")
        print(f"Log saved to: {result['log_file']}")
        print("\nStructured Log Preview:")
        print(json.dumps(result["structured_log"], indent=2)[:500] + "...")
    else:
        print(f"\nError: {result['error']}")
        print(f"Error type: {result['error_type']}") 