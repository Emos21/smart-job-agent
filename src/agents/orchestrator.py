from dataclasses import dataclass
from typing import Any

from .scout import create_scout_agent
from .forge import create_forge_agent
from .match import create_match_agent
from .coach import create_coach_agent


@dataclass
class AgentResult:
    """Result from a single agent's execution."""
    agent_name: str
    output: str
    success: bool


class Orchestrator:
    """Coordinates multiple specialized agents to handle complex tasks.

    The Orchestrator is the brain of KaziAI's multi-agent system.
    It decides which agents to dispatch based on the user's request,
    passes context between agents, and assembles the final output.

    Agent pipeline:
      Scout  →  finds jobs and researches companies
      Match  →  analyzes JD vs resume compatibility
      Forge  →  writes cover letter and rewrites resume
      Coach  →  prepares interview questions and strategy
    """

    def __init__(self, provider: str = "groq", model: str | None = None):
        self.provider = provider
        self.model = model
        self._results: list[AgentResult] = []

    @property
    def results(self) -> list[AgentResult]:
        return self._results

    def _run_agent(self, agent, task: str) -> AgentResult:
        """Run a single agent and capture its result."""
        try:
            output = agent.run(task)
            result = AgentResult(
                agent_name=agent.name,
                output=output,
                success=True,
            )
        except Exception as e:
            result = AgentResult(
                agent_name=agent.name,
                output=f"Agent failed: {str(e)}",
                success=False,
            )
        self._results.append(result)
        return result

    def search_jobs(self, keywords: list[str]) -> AgentResult:
        """Dispatch Scout agent to find jobs."""
        agent = create_scout_agent(self.provider, self.model)
        task = (
            f"Search for jobs matching these keywords: {', '.join(keywords)}. "
            f"Find the top results and research the most promising companies."
        )
        return self._run_agent(agent, task)

    def analyze_match(
        self, jd_text: str, resume_path: str
    ) -> AgentResult:
        """Dispatch Match agent to analyze job compatibility."""
        agent = create_match_agent(self.provider, self.model)
        task = (
            f"Analyze this job description against the candidate's resume.\n\n"
            f"Job Description:\n{jd_text}\n\n"
            f"Resume file path: {resume_path}\n\n"
            f"Parse both, match skills, score ATS compatibility, and "
            f"produce a detailed analysis."
        )
        return self._run_agent(agent, task)

    def write_materials(
        self,
        jd_text: str,
        resume_text: str,
        analysis: str,
    ) -> AgentResult:
        """Dispatch Forge agent to write application materials."""
        agent = create_forge_agent(self.provider, self.model)
        task = (
            f"Write application materials based on this analysis.\n\n"
            f"Job Description:\n{jd_text[:2000]}\n\n"
            f"Resume:\n{resume_text[:2000]}\n\n"
            f"Previous Analysis:\n{analysis[:2000]}\n\n"
            f"Rewrite the resume bullets to match the JD and generate "
            f"a tailored cover letter."
        )
        return self._run_agent(agent, task)

    def prep_interview(
        self,
        role: str,
        company: str,
        analysis: str,
    ) -> AgentResult:
        """Dispatch Coach agent for interview preparation."""
        agent = create_coach_agent(self.provider, self.model)
        task = (
            f"Prepare interview questions for the {role} role at {company}.\n\n"
            f"Analysis context:\n{analysis[:2000]}\n\n"
            f"Generate likely interview questions with talking points "
            f"and strategic advice."
        )
        return self._run_agent(agent, task)

    def full_pipeline(
        self,
        jd_text: str,
        resume_path: str,
        resume_text: str,
        role: str = "Software Engineer",
        company: str = "the company",
    ) -> dict[str, Any]:
        """Run the full multi-agent pipeline.

        Scout → Match → Forge → Coach
        Each agent's output feeds into the next.
        """
        self._results.clear()

        print("=" * 60)
        print("KAZI AI — MULTI-AGENT PIPELINE")
        print(f"Role: {role} | Company: {company}")
        print("=" * 60)

        # Step 1: Match Agent — analyze compatibility
        print("\n[1/3] Dispatching Match Agent...")
        match_result = self.analyze_match(jd_text, resume_path)

        # Step 2: Forge Agent — write materials
        print("\n[2/3] Dispatching Forge Agent...")
        forge_result = self.write_materials(
            jd_text, resume_text, match_result.output
        )

        # Step 3: Coach Agent — prep interview
        print("\n[3/3] Dispatching Coach Agent...")
        coach_result = self.prep_interview(
            role, company, match_result.output
        )

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)

        return {
            "analysis": match_result.output,
            "materials": forge_result.output,
            "interview_prep": coach_result.output,
            "all_results": self._results,
        }
