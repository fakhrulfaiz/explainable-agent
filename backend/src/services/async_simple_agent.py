from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
import json
import os
import asyncio
from datetime import datetime
try:
    from explainer import Explainer
except ImportError:
    from .explainer import Explainer


class AsyncSimpleAgentState(MessagesState):
    """Simplified state for async agent"""
    query: str
    steps: List[Dict[str, Any]]
    step_counter: int


class AsyncSimpleAgent:
    """Async SQL Agent that runs explainer in background without blocking"""
    
    def __init__(self, llm, db_path: str, logs_dir: str = None):
        self.llm = llm
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.db = SQLDatabase(self.engine)
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.tools = self.toolkit.get_tools()
        
        # Initialize explainer
        self.explainer = Explainer(llm)
        
        self.logs_dir = logs_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Create the simplified graph - no explainer node in main flow
        self.graph = self.create_graph()
    
    def create_graph(self):
        """Create simplified graph: agent -> tools -> agent (explainer runs in background)"""
        graph = StateGraph(AsyncSimpleAgentState)
        
        # Add nodes - no explainer node
        graph.add_node("agent", self.agent_node)
        graph.add_node("tools", self.tools_node)
        
        # Add edges - simplified flow without explainer blocking
        graph.set_entry_point("agent")
        
        # Agent decides whether to use tools or end
        graph.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # Tools -> back to agent (explainer runs separately)
        graph.add_edge("tools", "agent")
        
        return graph.compile()
    
    def should_continue(self, state: AsyncSimpleAgentState):
        """Check if agent wants to continue with tools or finish"""
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        else:
            return "end"
    
    def agent_node(self, state: AsyncSimpleAgentState):
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
            "query": state.get("query", ""),
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0)
        }
    
    def tools_node(self, state: AsyncSimpleAgentState):
        """Execute tools and capture step information"""
        messages = state["messages"]
        last_message = messages[-1]
        
        steps = state.get("steps", [])
        step_counter = state.get("step_counter", 0)
        
        # Execute tools
        tool_node = ToolNode(tools=self.tools)
        result = tool_node.invoke({"messages": messages})
        
        # Capture step information
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
            "query": state.get("query", ""),
            "steps": steps,
            "step_counter": step_counter
        }
    
    async def explain_step_async(self, step_info: Dict[str, Any]):
        """Async version of explainer that doesn't block main flow"""
        try:
            # Convert sync explainer to async
            explanation = await asyncio.to_thread(
                self.explainer.explain_step, 
                step_info
            )
            
            # Update the step with explanation
            step_info.update({
                "decision": explanation.decision,
                "reasoning": explanation.reasoning,
                "why_chosen": explanation.why_chosen,
                "confidence": explanation.confidence
            })
            
            return explanation
        except Exception as e:
            # Fallback explanation
            step_info.update({
                "decision": f"Error in explanation: {str(e)}",
                "reasoning": "Unable to generate explanation",
                "why_chosen": "Error occurred",
                "confidence": 0.5
            })
            return None
    
    async def explain_final_result_async(self, steps: List[Dict], final_answer: str, user_query: str):
        """Async version of final result explainer"""
        try:
            explanation = await asyncio.to_thread(
                self.explainer.explain_final_result,
                steps, final_answer, user_query
            )
            return explanation
        except Exception as e:
            # Return a basic explanation on error
            from .explainer import FinalExplanation
            return FinalExplanation(
                summary="Error in final analysis",
                details=final_answer,
                source="Agent processing",
                inference="Partial completion",
                extra_explanation=f"Error: {str(e)}",
                confidence=0.5
            )

    async def process_query_async(self, user_query: str):
        """Process query with background async explanations"""
        try:
            start_time = datetime.now()
            
            initial_state = AsyncSimpleAgentState(
                messages=[HumanMessage(content=user_query)],
                query=user_query,
                steps=[],
                step_counter=0
            )
            
            # Execute the main graph - no explanations blocking
            events = []
            async for event in self.graph.astream(initial_state, stream_mode="values"):
                events.append(event)
            
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
            
            # Start background explanation tasks
            explanation_tasks = []
            
            # Explain each step in background
            for step in steps:
                task = asyncio.create_task(self.explain_step_async(step))
                explanation_tasks.append(task)
            
            # Generate final explanation in background
            final_explanation_task = asyncio.create_task(
                self.explain_final_result_async(steps, final_answer, user_query)
            )
            
            # Wait for all explanations to complete (with timeout)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*explanation_tasks, final_explanation_task),
                    timeout=30.0  # 30 second timeout for explanations
                )
            except asyncio.TimeoutError:
                print("Warning: Explanations timed out, proceeding without some explanations")
            
            # Get final explanation result
            final_explanation = await final_explanation_task
            
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
            
            # Create structured log
            structured_log = {
                "question": user_query,
                "steps": steps,
                "final_structured_result": final_explanation.model_dump(),
                "total_time": total_time,
                "overall_confidence": overall_confidence
            }
            
            # Save log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.logs_dir, f"async_simple_agent_interaction_{timestamp}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(structured_log, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "response": final_answer if final_answer else "No clear response generated",
                "structured_log": structured_log,
                "log_file": log_file,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def process_query(self, user_query: str):
        """Sync wrapper for async process_query"""
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to create a task
                # This happens when called from async context
                return asyncio.create_task(self.process_query_async(user_query))
            else:
                # If no loop running, run in new loop
                return loop.run_until_complete(self.process_query_async(user_query))
        except RuntimeError:
            # No event loop exists, create new one
            return asyncio.run(self.process_query_async(user_query))


if __name__ == "__main__":
    # Test the async simple agent
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
    
    # Create async simple agent
    agent = AsyncSimpleAgent(llm=llm, db_path=db_path)
    
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
