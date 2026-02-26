"""Delegate tool: allows agents to invoke other agents mid-execution.

Safety guards:
- depth >= 1 → refuse (no recursive delegation)
- total_runs[0] >= 5 → refuse (global cap per dispatch)
- sub-agents get NO delegate tool (only memory tools)
"""

from typing import Any, Callable

from .base import Tool


class DelegateToAgentTool(Tool):
    """Tool that lets an agent delegate a sub-task to another agent."""

    def __init__(self):
        self._user_id: int | None = None
        self._message_bus = None
        self._depth: int = 0
        self._total_runs: list[int] = [0]  # mutable shared counter
        self._provider: str = "groq"
        self._model: str | None = None
        self._cancel_check: Callable[[], bool] | None = None

    def set_context(
        self,
        user_id: int | None,
        message_bus,
        depth: int,
        total_runs: list[int],
        provider: str = "groq",
        model: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self._user_id = user_id
        self._message_bus = message_bus
        self._depth = depth
        self._total_runs = total_runs
        self._provider = provider
        self._model = model
        self._cancel_check = cancel_check

    @property
    def name(self) -> str:
        return "delegate_to_agent"

    @property
    def description(self) -> str:
        return (
            "Delegate a sub-task to another specialized agent. "
            "Use when you need data or analysis from another agent's expertise. "
            "Scout finds jobs, Match analyzes compatibility, "
            "Forge writes materials, Coach prepares interviews."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["scout", "match", "forge", "coach"],
                    "description": "Which agent to delegate to",
                },
                "task_description": {
                    "type": "string",
                    "description": "What you need the other agent to do",
                },
            },
            "required": ["agent_name", "task_description"],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        agent_name = kwargs.get("agent_name", "")
        task_description = kwargs.get("task_description", "")

        if not agent_name or not task_description:
            return {"success": False, "error": "agent_name and task_description are required"}

        # Safety: no recursive delegation
        if self._depth >= 1:
            return {
                "success": False,
                "error": "Cannot delegate from a sub-agent (max depth 1)",
            }

        # Safety: global run cap
        if self._total_runs[0] >= 5:
            return {
                "success": False,
                "error": "Delegation limit reached (max 5 sub-agent runs per dispatch)",
            }

        # Import here to avoid circular imports
        from ..agents.orchestrator import Orchestrator

        factory = Orchestrator.AGENT_FACTORIES.get(agent_name)
        if not factory:
            return {"success": False, "error": f"Unknown agent: {agent_name}"}

        # Increment global counter
        self._total_runs[0] += 1

        try:
            # Create sub-agent with NO delegate tool (only memory tools)
            agent = factory(self._provider, self._model)

            # Register memory tools if we have a user
            if self._user_id:
                try:
                    from .memory_tools import RecallMemoryTool, StoreMemoryTool, RecallTraceTool

                    recall = RecallMemoryTool()
                    recall.set_user_id(self._user_id)
                    store = StoreMemoryTool()
                    store.set_user_id(self._user_id)
                    recall_trace = RecallTraceTool()
                    recall_trace.set_user_id(self._user_id)
                    agent.registry.register(recall)
                    agent.registry.register(store)
                    agent.registry.register(recall_trace)
                except ImportError:
                    pass

            # Create trace for sub-agent
            trace_id = None
            if self._user_id:
                try:
                    from .. import database as db

                    trace_id = db.create_trace(
                        user_id=self._user_id,
                        conversation_id=None,
                        agent_name=agent_name,
                        intent="delegation",
                        task=task_description[:2000],
                    )
                except Exception:
                    pass

            # Run the sub-agent
            result = agent.run(
                task_description,
                trace_id=trace_id,
                message_bus=self._message_bus,
                cancel_check=self._cancel_check,
            )

            return {
                "success": True,
                "agent": agent_name,
                "output": result[:3000],
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Delegation to {agent_name} failed: {str(e)[:500]}",
            }
