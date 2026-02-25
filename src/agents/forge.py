from ..tools.base import ToolRegistry
from ..tools.cover_letter import CoverLetterTool
from ..tools.resume_rewriter import ResumeRewriterTool
from .base_agent import BaseAgent


class ForgeAgent(BaseAgent):
    """Crafts application materials tailored to specific jobs.

    The Forge agent writes cover letters and rewrites resume sections
    to match a target job description's language and requirements.
    """

    @property
    def name(self) -> str:
        return "forge"

    @property
    def role(self) -> str:
        return "Application material writer"

    @property
    def system_prompt(self) -> str:
        return """You are the Forge Agent in the KaziAI career platform.
Your job is to craft compelling application materials.

Available tools:
{tool_descriptions}

## Your workflow
1. Take the job analysis results and candidate background
2. Rewrite resume bullets to align with the JD's language
3. Generate a tailored cover letter highlighting relevant strengths
4. Provide the materials in a clean, ready-to-use format

## Writing guidelines
- Use strong action verbs (built, designed, led, optimized)
- Include quantified achievements where possible
- Mirror the JD's terminology naturally
- Never fabricate experience — only reframe what exists
- Be concise and specific, not generic

When done, respond with FINAL_ANSWER followed by the crafted materials."""


def create_forge_agent(provider: str = "groq", model: str | None = None) -> ForgeAgent:
    """Factory function to create a Forge agent with its tools."""
    registry = ToolRegistry()
    registry.register(CoverLetterTool())
    registry.register(ResumeRewriterTool())
    return ForgeAgent(registry=registry, provider=provider, model=model)
