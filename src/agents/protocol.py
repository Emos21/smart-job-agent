"""Structured agent communication protocol.

Agents communicate via typed AgentMessage objects through a MessageBus,
replacing raw string concatenation with structured data flow.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentMessage:
    """A typed message between agents or between an agent and the orchestrator.

    Message types:
    - request: User or orchestrator task request
    - response: Agent output with confidence
    - observation: Evaluator notes, status updates
    - delegate: Agent requesting orchestrator to invoke another agent
    - error: Agent failure report
    - debate_position: Agent's position in a negotiation round
    - consensus: Final consensus from negotiation
    """
    sender: str           # "scout", "match", "forge", "coach", "orchestrator", "user", "negotiator"
    receiver: str         # target agent or "orchestrator" for routing
    msg_type: str         # "request", "response", "observation", "delegate", "error", "debate_position", "consensus"
    payload: dict         # structured data (not raw strings)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    trace_id: int | None = None


class MessageBus:
    """In-memory pub/sub for agent communication within a single dispatch session.

    Agents post messages to the bus. The orchestrator reads messages to build
    structured context for subsequent agents, handle delegation requests, and
    track observations.
    """

    def __init__(self):
        self._messages: list[AgentMessage] = []

    def send(self, msg: AgentMessage) -> None:
        """Post a message to the bus."""
        self._messages.append(msg)

    def get_for(self, receiver: str) -> list[AgentMessage]:
        """Get all messages addressed to a specific receiver."""
        return [m for m in self._messages if m.receiver == receiver]

    def get_observations(self) -> list[AgentMessage]:
        """Get all observation-type messages (evaluator notes, status updates)."""
        return [m for m in self._messages if m.msg_type == "observation"]

    def get_delegations(self) -> list[AgentMessage]:
        """Get all delegation requests (agent asking orchestrator to invoke another agent)."""
        return [m for m in self._messages if m.msg_type == "delegate"]

    def get_responses(self) -> list[AgentMessage]:
        """Get all response messages from agents."""
        return [m for m in self._messages if m.msg_type == "response"]

    def get_context_for(self, receiver: str) -> str:
        """Build a prompt-injectable context string from messages relevant to a receiver.

        Collects all response messages from prior agents and any observations,
        then formats them as structured context blocks.
        """
        parts = []

        for msg in self._messages:
            if msg.msg_type == "response" and msg.sender != receiver:
                output = msg.payload.get("output", "")
                confidence = msg.payload.get("confidence")
                if output:
                    header = f"--- {msg.sender.upper()} AGENT RESULTS ---"
                    if confidence is not None:
                        header += f" (confidence: {confidence:.0%})"
                    parts.append(f"{header}\n{output}")

            elif msg.msg_type == "observation":
                parts.append(f"[Note] {msg.payload.get('note', '')}")

        if not parts:
            return ""

        return "\n\nCONTEXT FROM PREVIOUS AGENTS:\n" + "\n\n".join(parts)

    def get_debate_messages(self) -> list[AgentMessage]:
        """Get all debate-related messages (positions and consensus)."""
        return [m for m in self._messages if m.msg_type in ("debate_position", "consensus")]

    @property
    def all_messages(self) -> list[AgentMessage]:
        """Read-only access to all messages."""
        return list(self._messages)
