from ..tools.base import ToolRegistry
from ..tools.interview_prep import InterviewPrepTool
from .base_agent import BaseAgent


class CoachAgent(BaseAgent):
    """Prepares candidates for interviews.

    The Coach agent generates interview questions, provides
    talking points, and gives strategic advice for the interview.
    """

    @property
    def name(self) -> str:
        return "coach"

    @property
    def role(self) -> str:
        return "Interview preparation and coaching"

    @property
    def system_prompt(self) -> str:
        return """You are the Coach Agent in the KaziAI career platform.
Your job is to prepare candidates for their interviews.

Available tools:
{tool_descriptions}

## Your workflow
1. Generate likely interview questions based on the role and company
2. Match questions to the candidate's experience for talking points
3. Identify areas where the candidate needs to prepare extra
4. Provide strategic advice for the interview

## Coaching guidelines
- Focus on the candidate's real strengths
- Be honest about gaps but frame them positively
- Suggest the STAR method for behavioral questions
- Remind them to prepare questions to ask the interviewer
- Include salary negotiation advice if relevant

When done, respond with FINAL_ANSWER followed by your prep guide."""


def create_coach_agent(provider: str = "groq", model: str | None = None) -> CoachAgent:
    """Factory function to create a Coach agent with its tools."""
    registry = ToolRegistry()
    registry.register(InterviewPrepTool())
    return CoachAgent(registry=registry, provider=provider, model=model)
