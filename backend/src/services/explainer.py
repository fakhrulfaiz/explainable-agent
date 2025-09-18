from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import json
from datetime import datetime


class StepExplanation(BaseModel):
    """Structured explanation for a single agent step"""
    decision: str = Field(description="Brief description of what was decided")
    reasoning: str = Field(description="Detailed explanation of why this step makes sense")
    why_chosen: str = Field(description="Why this specific tool/action was selected")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level (0.0 to 1.0)")


class FinalExplanation(BaseModel):
    """Structured explanation for the final result"""
    summary: str = Field(description="Overall summary of what the agent accomplished")
    details: str = Field(description="Detailed explanation of the final result")
    source: str = Field(description="Where the information came from")
    inference: str = Field(description="What can be inferred from the results")
    extra_explanation: str = Field(description="Additional context that might be helpful")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score", default=0.8)


class Explainer:
    """Agent that explains decisions and reasoning for other agents' actions"""
    
    def __init__(self, llm):
        self.llm = llm
        self.system_prompt = """You are an Explainer that analyzes and explains the decisions and reasoning behind other agents' actions.

Your role is to:
1. Analyze each step taken by agents
2. Explain WHY a particular tool or action was chosen
3. Provide reasoning for the decision-making process
4. Assess confidence levels for actions taken
5. Generate educational explanations for users

For each step, provide:
- decision: Brief description of what was decided
- reasoning: Detailed explanation of why this step makes sense
- why_chosen: Why this specific tool/action was selected
- confidence: Confidence level (0.0 to 1.0)

Be concise but thorough. Focus on educational value and clarity."""

    def explain_step(self, step_info: Dict[str, Any]) -> StepExplanation:
        """Explain a single step using structured output"""
        
        prompt = f"""
Analyze this agent step and provide an explanation:

Step Information:
- Tool/Action: {step_info.get('tool_name', 'Unknown')}
- Input: {step_info.get('input', {})}
- Output: {step_info.get('output', 'No output available')}
- Context: {step_info.get('context', 'User query about database')}

Provide a structured explanation with:
- decision: Brief description of what was decided
- reasoning: Detailed explanation of why this step makes sense in the context
- why_chosen: Why this specific tool was selected over alternatives
- confidence: Confidence level (0.0 to 1.0) for this decision

Focus on educational value and help the user understand the agent's thought process.
"""

        try:
         
            model_with_structure = self.llm.with_structured_output(StepExplanation)
            
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]
            
            explanation = model_with_structure.invoke(messages)
            return explanation
            
        except Exception as e:
            # Fallback to default structure if anything fails
            return StepExplanation(
                decision=f"Error analyzing step: {str(e)}",
                reasoning="Unable to provide detailed reasoning due to processing error",
                why_chosen="Default analysis due to error",
                confidence=0.5
            )

    def explain_final_result(self, all_steps: List[Dict], final_answer: str, user_query: str) -> FinalExplanation:
        """Generate explanation for the final result using structured output"""
        
        prompt = f"""
Analyze the complete agent interaction and provide a final explanation:

User Query: {user_query}
Number of Steps: {len(all_steps)}
Final Answer: {final_answer}

All Steps Summary:
{json.dumps([{
    'step': i+1, 
    'tool': step.get('tool_name', 'Unknown'),
} for i, step in enumerate(all_steps)], indent=2)}

Provide a structured final explanation with:
- summary: Overall summary of what the agent accomplished, if the result has image link, use format ![Alt text](image_link)
- details: Detailed explanation of the final result
- source: Where the information came from
- inference: What can be inferred from the results
- extra_explanation: Additional context that might be helpful

Make it educational and help users understand what happened overall.
"""

        try:
            # Use structured output to get Pydantic object directly
            model_with_structure = self.llm.with_structured_output(FinalExplanation)
            
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ]
            
            explanation = model_with_structure.invoke(messages)
            return explanation
            
        except Exception as e:
            # Fallback to default structure if anything fails
            return FinalExplanation(
                summary="Error in final analysis",
                details=final_answer,
                source="Agent processing",
                inference="Partial completion",
                extra_explanation=f"Error occurred during final analysis: {str(e)}",
                confidence=0.5
            ) 