from ..tools.base import ToolRegistry
from ..tools.job_search import JobSearchTool
from ..tools.company_researcher import CompanyResearcherTool
from .base_agent import BaseAgent


class ScoutAgent(BaseAgent):
    """Finds and researches job opportunities.

    The Scout agent searches job boards, filters results by relevance,
    and gathers company intelligence for each match.
    """

    @property
    def name(self) -> str:
        return "scout"

    @property
    def role(self) -> str:
        return "Job discovery and company research"

    @property
    def system_prompt(self) -> str:
        return """You are the Scout Agent in the KaziAI career platform.
Your job is to find relevant job opportunities and research companies.

Available tools:
{tool_descriptions}

## Your workflow
1. Search for jobs using the provided keywords/skills
2. Research the companies behind the most promising results
3. Compile a report of the best matches with company context

When done, respond with FINAL_ANSWER followed by your findings in a
structured format with job listings and company insights."""


def create_scout_agent(provider: str = "groq", model: str | None = None) -> ScoutAgent:
    """Factory function to create a Scout agent with its tools."""
    registry = ToolRegistry()
    registry.register(JobSearchTool())
    registry.register(CompanyResearcherTool())
    return ScoutAgent(registry=registry, provider=provider, model=model)
