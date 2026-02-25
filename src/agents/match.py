from ..tools.base import ToolRegistry
from ..tools.jd_parser import JDParserTool
from ..tools.resume_analyzer import ResumeAnalyzerTool
from ..tools.skills_matcher import SkillsMatcherTool
from ..tools.ats_scorer import ATSScorerTool
from .base_agent import BaseAgent


class MatchAgent(BaseAgent):
    """Analyzes compatibility between a candidate and a job.

    The Match agent parses job descriptions, analyzes resumes,
    scores ATS compatibility, and produces detailed gap analysis.
    """

    @property
    def name(self) -> str:
        return "match"

    @property
    def role(self) -> str:
        return "Skills analysis and ATS scoring"

    @property
    def system_prompt(self) -> str:
        return """You are the Match Agent in the KaziAI career platform.
Your job is to analyze how well a candidate matches a job.

Available tools:
{tool_descriptions}

## Your workflow
1. Parse the job description to extract requirements and keywords
2. Analyze the candidate's resume to extract their skills and experience
3. Run skills matching to find overlaps and gaps
4. Score the resume against ATS criteria
5. Compile a detailed compatibility report

## Analysis guidelines
- Be specific about which skills match and which don't
- Provide actionable suggestions for gaps
- Include the ATS score with concrete improvement steps
- Separate required vs. preferred skill gaps

When done, respond with FINAL_ANSWER followed by your analysis report."""


def create_match_agent(provider: str = "groq", model: str | None = None) -> MatchAgent:
    """Factory function to create a Match agent with its tools."""
    registry = ToolRegistry()
    registry.register(JDParserTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(SkillsMatcherTool())
    registry.register(ATSScorerTool())
    return MatchAgent(registry=registry, provider=provider, model=model)
