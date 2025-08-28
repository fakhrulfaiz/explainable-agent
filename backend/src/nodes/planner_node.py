from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
import json


class FeedbackResponse(BaseModel):
    """Model for handling user feedback responses"""
    response_type: Literal["answer", "replan", "cancel"] = Field(description="Type of response: answer for direct answers, replan for creating new plans, cancel for cancellation")
    content: str = Field(description="Content that can hold either the direct answer to user's question, a revised plan, or a general response")
    new_query: Optional[str] = Field(description="New query if the user requested a different question")


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
        
        try:
            # Get tool descriptions for the prompt without binding tools
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
            
            replan_prompt = f"""You are an intelligent AI assistant handling user feedback. 
            The human has provided feedback on your previous plan. Carefully analyze their feedback to determine the appropriate response.
            
            DECISION FRAMEWORK:
            1. If the human is asking a QUESTION or requesting CLARIFICATION about the current plan/process:
               - Set response_type: "answer"
               - Put your answer in "content"
            
            2. If the human wants to MODIFY, CHANGE, or IMPROVE the plan:
               - Set response_type: "replan" 
               - Put the revised plan directly in "content"
               - Set "new_query" if they requested a different question
               - Here is the planning prompt: Create a concise plan that outlines the specific steps needed to answer this query. 
               Reference the actual tool names available and explain when each would be used.
               Format your response as a clear, numbered plan with proper line breaks between steps. Each step should be on its own line starting with a number.
            
            3. If the human wants to CANCEL or STOP:
               - Set response_type: "cancel"
               - Put cancellation message in "content"
            
            Available tools for planning:
            {tool_descriptions}

            Original query: {user_query}
            Previous plan: {state.get('plan', 'No previous plan')}
            Human feedback: {human_feedback}
            
            EXAMPLES:
            - "What does this plan do?" → response_type: "answer", content: "This plan will..."
            - "Can you explain step 2?" → response_type: "answer", content: "Step 2 does..."
            - "Change the query to show all artists" → response_type: "replan", content: "1. Use sql_db_list_tables to get all tables\n2. Use sql_db_schema to examine artist table structure\n3. Use sql_db_query to select all artists", new_query: "show all artists"
            - "Make the plan simpler" → response_type: "replan", content: "1. Use sql_db_query to get the answer directly"
            - "Cancel this" → response_type: "cancel", content: "Operation cancelled"
            
            Respond with a FeedbackResponse object choosing the most appropriate response type.
            """
            
            feedback_messages = [
                SystemMessage(content=replan_prompt),
            ]
            
            llm_with_structure = self.llm.with_structured_output(FeedbackResponse)
            response = llm_with_structure.invoke(state.get("messages") + feedback_messages)
            print(f"LLM Response: {response}")
            
            if response.response_type == "cancel":
                return {
                    "messages": messages,
                    "status": "cancelled"
                }
            elif response.response_type == "answer":
                answer_message = AIMessage(content=response.content)
                return {
                    "messages": messages + [answer_message],
                    "query": user_query,
                    "plan": state.get("plan", ""),
                    "steps": state.get("steps", []),
                    "step_counter": state.get("step_counter", 0),
                    "assistant_response": response.content,
                    "status": "feedback" 
                }
            elif response.response_type == "replan":
                plan = response.content
                user_query = response.new_query if response.new_query else user_query
                assistant_response = response.content
                return {
                    "messages": messages + [HumanMessage(content=user_query)],
                    "query": user_query,
                    "plan": plan,
                    "steps": state.get("steps", []),
                    "step_counter": state.get("step_counter", 0),
                    "assistant_response": assistant_response
                }
            else:
                plan = f"Revised plan based on feedback: {human_feedback}"
                
                return {
                    "messages": messages,
                    "query": user_query,
                    "plan": plan,
                    "steps": state.get("steps", []),
                    "step_counter": state.get("step_counter", 0)
                }
                
        except Exception as e:
            print(f"Error in feedback processing: {e}")
            plan = f"Revised plan based on feedback: {human_feedback}"
            
            return {
                "messages": messages,
                "query": user_query,
                "plan": plan,
                "steps": state.get("steps", []),
                "step_counter": state.get("step_counter", 0)
            }
    
    def _handle_initial_planning(self, state, messages, user_query):
        
        planning_prompt = f"""You are a database query planner. Analyze the user's request and create a step-by-step plan.
                            User Query: {user_query}

                            Create a concise plan that outlines the specific steps needed to answer this query.
                            Reference the actual tool names available and explain when each would be used.
                            Format your response as a clear, numbered plan with proper line breaks between steps. Each step should be on its own line starting with a number."""

        try:
            # Bind tools to LLM so it knows what's available (but don't let it call them yet)
            llm_with_tools = self.llm.bind_tools(self.tools)
            
            planning_messages = [
                SystemMessage(content="You are a helpful database query planner. You can see what tools are available but should only create a plan, not execute tools."),
                SystemMessage(content=planning_prompt)
            ]
            
            response = llm_with_tools.invoke(planning_messages)
            plan = response.content
            
        except Exception as e:
            print(f"Error in initial planning: {e}")
            plan = f"Simple plan: Analyze the query '{user_query}' using available database tools like sql_db_list_tables, sql_db_schema, and sql_db_query."
        
        return {
            "messages": messages,
            "query": user_query,
            "plan": plan,
            "steps": state.get("steps", []),
            "step_counter": state.get("step_counter", 0)
        }
