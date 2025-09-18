from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
import json


class FeedbackResponse(BaseModel):
    """Model for handling user feedback responses"""
    response_type: Literal["answer", "replan", "cancel"] = Field(description="Type of response: answer for direct answers, replan for creating new plans, cancel for cancellation")
    content: str = Field(description="Content that can hold either the direct answer to user's question, a revised plan, or a general response")
    new_query: Optional[str] = Field(default=None, description="New query if the user requested a different question")


class PlannerNode: 
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
    
    def execute(self, state):
        messages = state["messages"]
        user_query = state.get("query", "")
        status = state.get("status", "approved")

        if status == "cancelled":
            return {
                "messages": messages,
                "status": "cancelled"
            }
        
        if status == "feedback" and state.get("human_comment"):
            return self._handle_feedback(state, messages, user_query)
        else:
            return self._handle_initial_planning(state, messages, user_query)
    
    def _handle_feedback(self, state, messages, user_query):
        human_feedback = state.get('human_comment', '')
        
        # Add human feedback message once at the start for consistency
        updated_messages = messages + [HumanMessage(content=human_feedback)]
         
        try:
            # Get tool descriptions for the prompt without binding tools
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
            
            replan_prompt = f"""Analyze user feedback and respond appropriately. You must provide a JSON response with three fields: response_type, content, and new_query.

RESPONSE TYPES:
1. "answer" - User asks questions about the plan → Provide clear explanations
2. "replan" - If User wants changes, improvements, or points out inefficiencies → Create revised numbered plan using available tools. If user changes the original request, set new_query field.
3. "cancel" - User wants to stop → Confirm cancellation

REQUIRED FIELDS:
- response_type: One of "answer", "replan", or "cancel"
- content: Your response text
- new_query: Set to null unless user wants a completely different query (only for "replan" type when user changes the original request)

CONTEXT:
Query: {user_query}
Plan: {state.get('plan', 'No previous plan')}
Feedback: {human_feedback}
Tools: {tool_descriptions}

EXAMPLES:
- "What does step 2 do?" → response_type: "answer", content: "explain the step", new_query: null
- "Add error handling" → response_type: "replan", content: "create new plan with error handling", new_query: null
- "This seems redundant" → response_type: "answer", content: "Which step seems redundant for you?", new_query: null
- "Can we skip unnecessary steps?" → response_type: "replan", content: "streamline the approach", new_query: null
- "Change to show all artists" → response_type: "replan", content: "create new plan", new_query: "show all artists"
- "Cancel this" → response_type: "cancel", content: "confirm cancellation", new_query: null
- "Show 3 rows from database" → response_type: "answer", content: "ask user for which table they want to see the rows from", new_query: null

Be intuitive: If user suggests optimizations or questions efficiency, the system should always try to answer with your opinion first and then if user wants to change the plan,
consider replan. For vague feedback, ask for clarification. If user ask question, do you best to answer and DO NOT replan directly."""
            
            # Filter out previous system messages to avoid conflicts
            conversation_messages = [msg for msg in updated_messages 
                                   if not isinstance(msg, SystemMessage)]
            
            # Prepare messages with system message FIRST, then conversation history (including feedback)
            all_messages = [
                SystemMessage(content=replan_prompt)
            ] + conversation_messages
            
            llm_with_structure = self.llm.with_structured_output(FeedbackResponse)
            response = llm_with_structure.invoke(all_messages)
            print(f"LLM Response: {response}")
            print(f"Response Type: {response.response_type}")
            print(f"New Query: {response.new_query}")
          
            
            if response.response_type == "cancel":
                return {
                    "messages": updated_messages,
                    "query": user_query,
                    "plan": state.get("plan", ""),
                    "steps": state.get("steps", []),
                    "step_counter": state.get("step_counter", 0),
                    "assistant_response": response.content,
                    "status": "cancelled"
                }
            elif response.response_type == "answer":
                answer_message = AIMessage(content=response.content)
                return {
                    "messages": updated_messages + [answer_message],
                    "query": user_query,
                    "plan": state.get("plan", ""),
                    "steps": state.get("steps", []),
                    "step_counter": state.get("step_counter", 0),
                    "assistant_response": response.content,
                    "status": "feedback" 
                }
            elif response.response_type == "replan":
                plan = response.content
                new_query = response.new_query if response.new_query else user_query
                replan_message = AIMessage(content=response.content)
                return {
                    "messages": updated_messages + [replan_message],
                    "query": new_query,
                    "plan": plan,
                    "steps": [],  # Reset steps for new plan
                    "step_counter": 0,  # Reset counter for new plan
                    "assistant_response": response.content,
                    "status": "feedback"  # Require approval for new plan
                }
            else:
                # Fallback case - treat as replan
                plan = f"Revised plan based on feedback: {human_feedback}"
                fallback_message = AIMessage(content=plan)
                return {
                    "messages": updated_messages + [fallback_message],
                    "query": user_query,
                    "plan": plan,
                    "steps": [],  # Reset steps for new plan
                    "step_counter": 0,  # Reset counter
                    "assistant_response": plan,
                    "status": "feedback"
                }
                
        except Exception as e:
            print(f"Error in feedback processing: {e}")
            plan = f"Error processing feedback: {human_feedback}. Please try again."
            error_message = AIMessage(content=plan)
            
            return {
                "messages": updated_messages + [error_message],
                "query": user_query,
                "plan": state.get("plan", ""),  # Preserve original plan on error
                "steps": state.get("steps", []),  # Preserve steps on error
                "step_counter": state.get("step_counter", 0),
                "assistant_response": plan,
                "status": "feedback"  # Stay in feedback mode for retry
            }
    
    def _handle_initial_planning(self, state, messages, user_query):
        
        planning_prompt = f"""You are a database query planner. Analyze the user's request and create a step-by-step plan.
                            User Query: {user_query}

                            Create a concise plan that outlines the specific steps needed to answer this query.
                            Reference the actual tool names available and explain when each would be used.
                            Format your response as a clear, numbered plan with proper line breaks between steps. Each step should be on its own line starting with a number."""

        try:

            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])

            # Filter out previous system messages to avoid conflicts
            conversation_messages = [msg for msg in messages 
                                   if not isinstance(msg, SystemMessage)]
            
            # Prepare messages with system message FIRST, then conversation history
            all_messages = [
                SystemMessage(content=f"Available tools for planning:\n{tool_descriptions}"),
                SystemMessage(content=planning_prompt)
            ] + conversation_messages  # Include conversation history without system messages
            
            response = self.llm.invoke(all_messages)
            plan = response.content
            
        except Exception as e:
            print(f"Error in initial planning: {e}")
            plan = f"Simple plan: Analyze the query '{user_query}' using available database tools like sql_db_list_tables, sql_db_schema, and sql_db_query."
        
        return {
            "messages": messages + [AIMessage(content=plan)],
            "query": user_query,
            "plan": plan,
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0)
        }
