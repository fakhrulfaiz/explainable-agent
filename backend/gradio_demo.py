#!/usr/bin/env python3
"""
Interactive Gradio Demo for Explainable Agent with Human-in-the-Loop
"""

import os
import sys
import json
import gradio as gr
from dotenv import load_dotenv

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from langchain_openai import ChatOpenAI
from src.services.explainable_agent import ExplainableAgent

# Global variables to maintain state
agent = None
current_config = None
current_result = None

def initialize_agent():
    """Initialize the explainable agent"""
    global agent
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        return "❌ No OPENAI_API_KEY found. Please set it in your .env file"
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)
        db_path = os.path.join("src", "resource", "art.db")
        
        if not os.path.exists(db_path):
            return f"❌ Database not found at {db_path}"
        
        agent = ExplainableAgent(llm=llm, db_path=db_path)
        return "✅ Agent initialized successfully!"
    
    except Exception as e:
        return f"❌ Failed to initialize agent: {str(e)}"

def process_query(query):
    """Process a user query and handle interrupts"""
    global agent, current_config, current_result
    
    if not agent:
        init_msg = initialize_agent()
        if "❌" in init_msg:
            return init_msg, "", "", True
    
    if not query.strip():
        return "Please enter a query", "", "", True
    
    try:
        result = agent.process_query(query)
        current_result = result
        
        if result["success"]:
            if result.get("interrupted"):
                # Store config for continuation
                current_config = result["config"]
                
                plan_display = f"""
## 📋 Proposed Plan:
{result['plan']}

**The agent is waiting for your feedback. Choose an option below:**
"""
                
                return (
                    "🤖 Agent has created a plan and is waiting for your approval:",
                    plan_display,
                    "",  # Clear feedback box
                    False  # Enable feedback buttons
                )
            else:
                # Completed execution
                return format_completed_result(result), "", "", True
        else:
            return f"❌ Error: {result.get('error', 'Unknown error')}", "", "", True
            
    except Exception as e:
        return f"❌ Exception: {str(e)}", "", "", True

def approve_plan():
    """Approve the current plan and continue execution"""
    global agent, current_config
    
    if not agent or not current_config:
        return "❌ No active plan to approve", "", True
    
    try:
        events = agent.approve_and_continue(current_config)
        # Get the final result
        result = format_execution_result(events)
        
        # Clear state
        current_config = None
        
        return result, "", True
        
    except Exception as e:
        return f"❌ Error approving plan: {str(e)}", "", True

def provide_feedback(feedback):
    """Provide feedback for plan revision"""
    global agent, current_config
    
    if not agent or not current_config:
        return "❌ No active plan to provide feedback for", "", True
    
    if not feedback.strip():
        return "Please provide feedback", "", False
    
    try:
        if "cancel" in feedback.lower():
            events = agent.continue_with_feedback(feedback, "cancelled", current_config)
            current_config = None
            return "🚫 Operation cancelled", "", True
        else:
            events = agent.continue_with_feedback(feedback, "feedback", current_config)
            result = format_execution_result(events)
            current_config = None
            return result, "", True
            
    except Exception as e:
        return f"❌ Error processing feedback: {str(e)}", "", True

def format_execution_result(events):
    """Format the execution result for display"""
    if not events:
        return "No execution events"
    
    final_state = events[-1] if events else {}
    
    # Extract final answer
    final_answer = ""
    if "messages" in final_state:
        for msg in reversed(final_state["messages"]):
            if (hasattr(msg, 'content') and msg.content and 
                type(msg).__name__ == 'AIMessage' and
                (not hasattr(msg, 'tool_calls') or not msg.tool_calls)):
                final_answer = msg.content
                break
    
    # Format steps
    steps = final_state.get("steps", [])
    steps_display = ""
    
    if steps:
        steps_display = "\n### 📊 Execution Steps:\n"
        for i, step in enumerate(steps[-3:], 1):  # Show last 3 steps
            steps_display += f"""
**Step {step.get('id', i)}: {step.get('type', 'Unknown')}**
- 🎯 Decision: {step.get('decision', 'N/A')}
- 💭 Reasoning: {step.get('reasoning', 'N/A')[:150]}...
- 🔧 Tool: {step.get('tool_name', 'N/A')}
- 📊 Confidence: {step.get('confidence', 0):.1%}
"""
    
    return f"""
## ✅ Execution Complete!

### 🎯 Final Answer:
{final_answer}

{steps_display}

### 📈 Summary:
- Total steps executed: {len(steps)}
- Plan: {final_state.get('plan', 'N/A')[:100]}...
"""

def format_completed_result(result):
    """Format completed result for display"""
    log = result.get("structured_log", {})
    
    steps_display = ""
    if log.get("steps"):
        steps_display = f"\n### 📊 Execution Summary:\n"
        steps_display += f"- Total steps: {len(log['steps'])}\n"
        steps_display += f"- Execution time: {log.get('total_time', 0):.2f}s\n"
        steps_display += f"- Overall confidence: {log.get('overall_confidence', 0):.1%}\n"
    
    return f"""
## ✅ Query Completed Successfully!

### 🎯 Response:
{result.get('response', 'No response')}

{steps_display}

### 📁 Log File:
{result.get('log_file', 'N/A')}
"""

# Create Gradio interface
def create_interface():
    """Create the Gradio interface"""
    
    with gr.Blocks(title="Explainable Agent Demo", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # 🤖 Explainable Agent with Human-in-the-Loop
        
        This demo shows an AI agent that:
        1. **Creates plans** for database queries
        2. **Asks for approval** before execution  
        3. **Accepts feedback** for plan revision
        4. **Explains each step** of execution
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                query_input = gr.Textbox(
                    label="📝 Enter your database query",
                    placeholder="e.g., Show me 3 rows from the paintings table",
                    lines=2
                )
                
                submit_btn = gr.Button("🚀 Submit Query", variant="primary")
                
                gr.Markdown("### 💬 Feedback for Plan Revision")
                feedback_input = gr.Textbox(
                    label="Provide feedback (or type 'cancel' to stop)",
                    placeholder="e.g., Make the plan more detailed, or add error handling",
                    lines=2,
                    interactive=False
                )
                
                with gr.Row():
                    approve_btn = gr.Button("✅ Approve Plan", variant="secondary", interactive=False)
                    feedback_btn = gr.Button("📝 Send Feedback", variant="secondary", interactive=False)
            
            with gr.Column(scale=3):
                status_output = gr.Markdown("Ready to process queries...")
                plan_output = gr.Markdown("")
        
        # Event handlers
        def on_submit(query):
            result = process_query(query)
            status, plan, feedback, buttons_disabled = result
            
            return (
                status,
                plan, 
                feedback,
                gr.update(interactive=not buttons_disabled),  # feedback_input
                gr.update(interactive=not buttons_disabled),  # approve_btn
                gr.update(interactive=not buttons_disabled),  # feedback_btn
            )
        
        def on_approve():
            result = approve_plan()
            status, feedback, buttons_disabled = result
            
            return (
                status,
                "",  # Clear plan
                feedback,
                gr.update(interactive=not buttons_disabled),  # feedback_input
                gr.update(interactive=not buttons_disabled),  # approve_btn
                gr.update(interactive=not buttons_disabled),  # feedback_btn
            )
        
        def on_feedback(feedback):
            result = provide_feedback(feedback)
            status, feedback_clear, buttons_disabled = result
            
            return (
                status,
                "",  # Clear plan
                feedback_clear,
                gr.update(interactive=not buttons_disabled),  # feedback_input
                gr.update(interactive=not buttons_disabled),  # approve_btn
                gr.update(interactive=not buttons_disabled),  # feedback_btn
            )
        
        # Wire up events
        submit_btn.click(
            on_submit,
            inputs=[query_input],
            outputs=[status_output, plan_output, feedback_input, feedback_input, approve_btn, feedback_btn]
        )
        
        approve_btn.click(
            on_approve,
            outputs=[status_output, plan_output, feedback_input, feedback_input, approve_btn, feedback_btn]
        )
        
        feedback_btn.click(
            on_feedback,
            inputs=[feedback_input],
            outputs=[status_output, plan_output, feedback_input, feedback_input, approve_btn, feedback_btn]
        )
        
        # Examples
        gr.Examples(
            examples=[
                ["Show me 3 rows from the paintings table"],
                ["What tables are in this database?"],
                ["Count the total number of paintings"],
                ["Show me paintings by a specific artist"]
            ],
            inputs=[query_input]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
