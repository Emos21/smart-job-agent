from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolResult:
    """Record of a single tool execution within the agent loop."""
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentStep:
    """One iteration of the ReAct loop: thought, action, observation."""
    step_number: int
    thought: str
    tool_call: ToolResult | None = None
    observation: str = ""


class AgentMemory:
    """Maintains context across the agent's reasoning steps.

    Stores the full history of the agent's thoughts, tool calls,
    and observations so it can reference earlier results when
    making decisions in later steps. This is what makes the agent
    stateful across its multi-step execution.
    """

    def __init__(self):
        self._steps: list[AgentStep] = []
        self._facts: dict[str, Any] = {}

    @property
    def steps(self) -> list[AgentStep]:
        return self._steps

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def add_step(self, step: AgentStep) -> None:
        """Record a completed reasoning step."""
        self._steps.append(step)

    def store_fact(self, key: str, value: Any) -> None:
        """Store a derived fact the agent discovered during execution.
        Facts persist across steps and can be referenced later."""
        self._facts[key] = value

    def get_fact(self, key: str) -> Any | None:
        """Retrieve a previously stored fact."""
        return self._facts.get(key)

    def get_all_facts(self) -> dict[str, Any]:
        """Return all stored facts."""
        return dict(self._facts)

    def get_history_summary(self) -> str:
        """Build a text summary of all steps for the LLM context.
        This is injected into the prompt so the agent remembers
        what it has already done."""
        if not self._steps:
            return "No previous steps."

        lines = []
        for step in self._steps:
            lines.append(f"Step {step.step_number}:")
            lines.append(f"  Thought: {step.thought}")
            if step.tool_call:
                lines.append(f"  Action: {step.tool_call.tool_name}({step.tool_call.arguments})")
                lines.append(f"  Observation: {step.observation[:500]}")
            lines.append("")

        return "\n".join(lines)

    def clear(self) -> None:
        """Reset memory for a new task."""
        self._steps.clear()
        self._facts.clear()
