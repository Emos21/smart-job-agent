from dataclasses import dataclass
from typing import Any, Callable

from .scout import create_scout_agent
from .forge import create_forge_agent
from .match import create_match_agent
from .coach import create_coach_agent
from .router import RoutingDecision
from .protocol import AgentMessage, MessageBus
from .. import database as db
from ..episodic_memory import EpisodicMemory, extract_memories_from_output


@dataclass
class AgentResult:
    """Result from a single agent's execution."""
    agent_name: str
    output: str
    success: bool
    trace_id: int | None = None


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

    AGENT_FACTORIES = {
        "scout": create_scout_agent,
        "match": create_match_agent,
        "forge": create_forge_agent,
        "coach": create_coach_agent,
    }

    def __init__(self, provider: str = "groq", model: str | None = None):
        self.provider = provider
        self.model = model
        self._results: list[AgentResult] = []

    @property
    def results(self) -> list[AgentResult]:
        return self._results

    def dispatch(
        self,
        routing: RoutingDecision,
        user_message: str,
        resume_text: str = "",
        profile: dict | None = None,
        history: list[dict] | None = None,
        on_agent_status: Any = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_agent_thought: Callable[[str, str, str], None] | None = None,
        on_evaluator: Callable[[dict], None] | None = None,
    ) -> list[AgentResult]:
        """Dispatch agents based on a routing decision.

        Runs agents in an evaluator-driven loop with structured communication
        via MessageBus. Calls on_agent_status(agent_name, status) if provided.

        Args:
            cancel_check: Optional callback returning True to stop dispatch
            on_agent_thought: Optional callback(agent_name, thought, tool_name) for reasoning
            on_evaluator: Optional callback(decision_dict) for evaluator events

        Returns list of AgentResult from all dispatched agents.
        """
        self._results.clear()
        bus = MessageBus()

        # Post user request to bus
        bus.send(AgentMessage(
            sender="user",
            receiver="orchestrator",
            msg_type="request",
            payload={"message": user_message, "intent": routing.intent},
        ))

        # Import evaluator (Phase 2) and learner (Phase 5) if available
        evaluator = None
        learner = None
        rl_trainer = None
        try:
            from .evaluator import PipelineEvaluator
            evaluator = PipelineEvaluator()
        except ImportError:
            pass
        try:
            from .learner import AgentLearner
            learner = AgentLearner()
        except ImportError:
            pass

        # Load RL trainer for tool hints (Phase 8)
        try:
            from ..rl.trainer import RLTrainer
            rl_trainer = RLTrainer()
        except ImportError:
            pass

        # Memory tools injection (Phase 4)
        memory_tools = []
        try:
            from ..tools.memory_tools import RecallMemoryTool, StoreMemoryTool, RecallTraceTool
            if user_id:
                recall = RecallMemoryTool()
                recall.set_user_id(user_id)
                store = StoreMemoryTool()
                store.set_user_id(user_id)
                recall_trace = RecallTraceTool()
                recall_trace.set_user_id(user_id)
                memory_tools = [recall, store, recall_trace]
        except ImportError:
            pass

        # Shared delegation counter (Phase 7 — Agent Self-Delegation)
        delegate_total_runs: list[int] = [0]

        remaining_agents = list(routing.agents)
        max_iterations = len(remaining_agents) + 3  # Allow up to 3 extra for loops/additions
        iteration = 0

        while remaining_agents and iteration < max_iterations:
            iteration += 1
            agent_name = remaining_agents.pop(0)

            factory = self.AGENT_FACTORIES.get(agent_name)
            if not factory:
                continue

            # Check cancellation
            if cancel_check and cancel_check():
                break

            if on_agent_status:
                on_agent_status(agent_name, "running")

            # Build task with structured bus context (replaces string concat)
            task = self._build_agent_task(
                agent_name=agent_name,
                user_message=user_message,
                extracted_context=routing.extracted_context,
                resume_text=resume_text,
                profile=profile,
                prior_output="",  # No longer using raw string; bus provides context
            )

            # Inject learned experience context (Phase 5)
            if learner and user_id:
                try:
                    expertise = learner.get_expertise_context(user_id, agent_name)
                    if expertise:
                        task = task + "\n\n" + expertise
                except Exception:
                    pass

            # Get RL tool hints (Phase 8)
            rl_hints = ""
            if rl_trainer and user_id:
                try:
                    rl_hints = rl_trainer.get_tool_hints(user_id, {
                        "query": user_message,
                        "agent_name": agent_name,
                        "profile": profile,
                    })
                except Exception:
                    pass

            # Create trace for this agent run
            trace_id = None
            if user_id:
                try:
                    trace_id = db.create_trace(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        agent_name=agent_name,
                        intent=routing.intent,
                        task=task,
                    )
                except Exception:
                    pass

            agent = factory(self.provider, self.model)

            # Register memory tools in agent's registry (Phase 4)
            for tool in memory_tools:
                agent.registry.register(tool)

            # Register delegate tool (Phase 7 — Agent Self-Delegation)
            try:
                from ..tools.delegate_tool import DelegateToAgentTool
                delegate_tool = DelegateToAgentTool()
                delegate_tool.set_context(
                    user_id=user_id,
                    message_bus=bus,
                    depth=0,
                    total_runs=delegate_total_runs,
                    provider=self.provider,
                    model=self.model,
                    cancel_check=cancel_check,
                )
                agent.registry.register(delegate_tool)
            except ImportError:
                pass

            # Build thought callback scoped to this agent
            thought_cb = None
            if on_agent_thought:
                _name = agent_name
                thought_cb = lambda thought, tool, _n=_name: on_agent_thought(_n, thought, tool)

            result = self._run_agent(
                agent, task,
                trace_id=trace_id,
                message_bus=bus,
                cancel_check=cancel_check,
                on_thought=thought_cb,
                rl_hints=rl_hints,
            )

            # Post result to message bus as structured response
            if result.success:
                bus.send(AgentMessage(
                    sender=agent_name,
                    receiver="orchestrator",
                    msg_type="response",
                    payload={
                        "output": result.output,
                        "confidence": 0.8,  # Default; agents can override
                        "needs_more_data": False,
                    },
                    trace_id=trace_id,
                ))

                # Extract and store memories from successful agent output
                if user_id:
                    try:
                        facts = extract_memories_from_output(result.output, user_message)
                        memory = EpisodicMemory(user_id)
                        for fact in facts:
                            memory.remember(
                                content=fact["content"],
                                category=fact["category"],
                                conversation_id=conversation_id,
                            )
                    except Exception:
                        pass
            else:
                bus.send(AgentMessage(
                    sender=agent_name,
                    receiver="orchestrator",
                    msg_type="error",
                    payload={"output": result.output},
                    trace_id=trace_id,
                ))

            if on_agent_status:
                status = "complete" if result.success else "failed"
                on_agent_status(agent_name, status)

            # Run evaluator (Phase 2) to decide next step
            if evaluator and result.success:
                try:
                    decision = evaluator.evaluate(
                        agent_result=result,
                        message_bus=bus,
                        remaining_agents=remaining_agents,
                        routing=routing,
                    )

                    # Post evaluator decision as observation
                    bus.send(AgentMessage(
                        sender="evaluator",
                        receiver="orchestrator",
                        msg_type="observation",
                        payload={
                            "note": f"[{decision.action}] {decision.reason}",
                            "action": decision.action,
                            "target": decision.target_agent,
                        },
                    ))

                    if on_evaluator:
                        on_evaluator({
                            "decision": decision.action,
                            "reason": decision.reason,
                            "target_agent": decision.target_agent,
                        })

                    if decision.action == "stop":
                        remaining_agents.clear()
                    elif decision.action == "skip_next" and remaining_agents:
                        skipped = remaining_agents.pop(0)
                        bus.send(AgentMessage(
                            sender="evaluator",
                            receiver="orchestrator",
                            msg_type="observation",
                            payload={"note": f"Skipped {skipped}: {decision.reason}"},
                        ))
                    elif decision.action == "loop_back" and decision.target_agent:
                        remaining_agents.insert(0, decision.target_agent)
                    elif decision.action == "add_agent" and decision.target_agent:
                        if decision.target_agent not in remaining_agents:
                            remaining_agents.append(decision.target_agent)
                    # "continue" → do nothing, proceed normally
                except Exception:
                    pass  # Evaluator failure shouldn't break the pipeline

            # Handle delegation requests from the bus
            for deleg in bus.get_delegations():
                target = deleg.payload.get("target_agent")
                if target and target not in remaining_agents and target in self.AGENT_FACTORIES:
                    remaining_agents.insert(0, target)

        # After all agents complete, run conflict detection and negotiation (Phase 8)
        try:
            from .negotiation import ConflictDetector, NegotiationSession
            detector = ConflictDetector()
            conflicts = detector.detect_conflicts(bus)

            if conflicts:
                for conflict in conflicts[:1]:  # Handle first conflict only
                    session = NegotiationSession(
                        conflict=conflict,
                        bus=bus,
                        conversation_id=conversation_id,
                    )
                    consensus = session.run()

                    # Post consensus to bus
                    bus.send(AgentMessage(
                        sender="negotiator",
                        receiver="orchestrator",
                        msg_type="consensus",
                        payload={
                            "reached": consensus.reached,
                            "position": consensus.position,
                            "confidence": consensus.confidence,
                            "dissenting_views": consensus.dissenting_views,
                            "rounds_taken": consensus.rounds_taken,
                        },
                    ))
        except ImportError:
            pass
        except Exception:
            pass

        return self._results

    def _build_agent_task(
        self,
        agent_name: str,
        user_message: str,
        extracted_context: dict,
        resume_text: str = "",
        profile: dict | None = None,
        prior_output: str = "",
    ) -> str:
        """Construct the right task string per agent type using extracted context."""
        company = extracted_context.get("company") or "the company"
        role = extracted_context.get("role") or (profile.get("target_role") if profile else "") or "the role"
        skills = extracted_context.get("skills") or []

        parts = [f"User request: {user_message}"]

        if profile:
            profile_parts = []
            if profile.get("target_role"):
                profile_parts.append(f"Target role: {profile['target_role']}")
            if profile.get("experience_level"):
                profile_parts.append(f"Experience: {profile['experience_level']}")
            if profile.get("skills"):
                profile_parts.append(f"Skills: {', '.join(profile['skills'][:15])}")
            if profile.get("location"):
                profile_parts.append(f"Location: {profile['location']}")
            if profile_parts:
                parts.append("User profile:\n" + "\n".join(profile_parts))

        if agent_name == "scout":
            keywords = skills or [role]
            parts.append(
                f"Search for jobs matching: {', '.join(keywords)}. "
                f"Focus on {role} roles{f' at {company}' if company != 'the company' else ''}. "
                f"Find the top results and research the most promising companies."
            )

        elif agent_name == "match":
            parts.append(f"Analyze compatibility for {role} at {company}.")
            if resume_text:
                parts.append(f"Resume:\n{resume_text[:3000]}")
            if extracted_context.get("has_jd"):
                parts.append("The job description was provided in the user's message above.")
            parts.append(
                "Parse the job requirements, analyze the resume, match skills, "
                "and score ATS compatibility. Produce a detailed analysis."
            )

        elif agent_name == "forge":
            parts.append(
                f"Write application materials for {role} at {company}. "
                f"Rewrite resume bullets to match the role and generate a tailored cover letter."
            )
            if resume_text:
                parts.append(f"Resume:\n{resume_text[:2000]}")

        elif agent_name == "coach":
            parts.append(
                f"Prepare interview questions for {role} at {company}. "
                f"Generate likely questions with talking points and strategic advice."
            )

        if prior_output:
            parts.append(f"Context from previous agents:{prior_output[:3000]}")

        return "\n\n".join(parts)

    def _run_agent(
        self,
        agent,
        task: str,
        trace_id: int | None = None,
        message_bus: MessageBus | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_thought: Callable[[str, str], None] | None = None,
        rl_hints: str = "",
    ) -> AgentResult:
        """Run a single agent and capture its result."""
        try:
            output = agent.run(
                task,
                trace_id=trace_id,
                message_bus=message_bus,
                cancel_check=cancel_check,
                on_thought=on_thought,
                rl_hints=rl_hints,
            )
            result = AgentResult(
                agent_name=agent.name,
                output=output,
                success=True,
                trace_id=trace_id,
            )
        except Exception as e:
            result = AgentResult(
                agent_name=agent.name,
                output=f"Agent failed: {str(e)}",
                success=False,
                trace_id=trace_id,
            )
            # Mark trace as failed
            if trace_id:
                try:
                    db.complete_trace(trace_id, "failed", str(e))
                except Exception:
                    pass
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
