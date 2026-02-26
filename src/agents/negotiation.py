"""Multi-agent negotiation system.

When agents produce conflicting outputs, a structured debate resolves disagreements:
- Round 1 (Opening): Each agent states position + evidence + confidence
- Round 2 (Rebuttal): Agents may CONCEDE, COUNTER, or REQUEST_DATA
- Round 3 (Final): Definitive positions if no consensus yet

Consensus rules:
- All concede → done
- Confidence convergence (within 0.15) → done
- After round 3 → highest confidence wins, dissenting views preserved
"""

import json
import os
import re
from dataclasses import dataclass, field

from openai import OpenAI
from dotenv import load_dotenv

from .protocol import AgentMessage, MessageBus
from .. import database as db

load_dotenv()

POSITIVE_KEYWORDS = {"excellent", "strong", "great", "perfect", "ideal", "recommended", "top", "best"}
NEGATIVE_KEYWORDS = {"poor", "weak", "bad", "avoid", "risky", "unlikely", "mismatch", "low"}


@dataclass
class Conflict:
    """A detected conflict between agent outputs."""
    agents: list[str]
    topic: str
    details: str
    confidence_gap: float = 0.0


@dataclass
class AgentPosition:
    """An agent's position in a negotiation round."""
    agent_name: str
    response_type: str  # "position", "concede", "counter", "request_data"
    position: str
    evidence: str
    confidence: float


@dataclass
class ConsensusResult:
    """Outcome of a negotiation session."""
    reached: bool
    position: str
    confidence: float
    dissenting_views: list[str] = field(default_factory=list)
    rounds_taken: int = 0


class ConflictDetector:
    """Scans MessageBus responses to detect conflicts between agents."""

    CONFIDENCE_THRESHOLD = 0.3
    SENTIMENT_THRESHOLD = 3  # Number of keyword matches

    def detect_conflicts(self, bus: MessageBus) -> list[Conflict]:
        """Scan all agent responses for conflicting outputs."""
        conflicts = []
        responses = bus.get_responses()

        if len(responses) < 2:
            return []

        # Check all pairs of responses
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                r1 = responses[i]
                r2 = responses[j]

                conflict = self._check_pair(r1, r2)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_pair(self, r1: AgentMessage, r2: AgentMessage) -> Conflict | None:
        """Check if two agent responses conflict."""
        c1 = r1.payload.get("confidence", 0.5)
        c2 = r2.payload.get("confidence", 0.5)
        o1 = (r1.payload.get("output") or "").lower()
        o2 = (r2.payload.get("output") or "").lower()

        # Check confidence divergence
        conf_gap = abs(c1 - c2)
        if conf_gap > self.CONFIDENCE_THRESHOLD:
            return Conflict(
                agents=[r1.sender, r2.sender],
                topic="confidence_divergence",
                details=f"{r1.sender} confidence {c1:.0%} vs {r2.sender} confidence {c2:.0%}",
                confidence_gap=conf_gap,
            )

        # Check sentiment contradiction
        pos1 = sum(1 for kw in POSITIVE_KEYWORDS if kw in o1)
        neg1 = sum(1 for kw in NEGATIVE_KEYWORDS if kw in o1)
        pos2 = sum(1 for kw in POSITIVE_KEYWORDS if kw in o2)
        neg2 = sum(1 for kw in NEGATIVE_KEYWORDS if kw in o2)

        # One agent positive, other negative
        if (pos1 >= self.SENTIMENT_THRESHOLD and neg2 >= self.SENTIMENT_THRESHOLD) or \
           (neg1 >= self.SENTIMENT_THRESHOLD and pos2 >= self.SENTIMENT_THRESHOLD):
            return Conflict(
                agents=[r1.sender, r2.sender],
                topic="sentiment_contradiction",
                details=f"{r1.sender} is {'positive' if pos1 > neg1 else 'negative'}, "
                        f"{r2.sender} is {'positive' if pos2 > neg2 else 'negative'}",
            )

        return None


class NegotiationSession:
    """Runs a structured debate between conflicting agents."""

    MAX_ROUNDS = 3

    def __init__(self, conflict: Conflict, bus: MessageBus, conversation_id: int | None = None):
        self.conflict = conflict
        self.bus = bus
        self.conversation_id = conversation_id
        self._client = None
        self._session_id = None
        self._positions: list[list[AgentPosition]] = []  # positions per round

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self._client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
        return self._client

    def run(self) -> ConsensusResult:
        """Execute the negotiation and return the consensus result.

        Yields events for frontend visualization.
        """
        if not self.client:
            return ConsensusResult(
                reached=False,
                position="Negotiation skipped — no LLM client",
                confidence=0.5,
            )

        # Create session in DB
        self._session_id = db.create_negotiation_session(
            conversation_id=self.conversation_id,
            topic=self.conflict.topic,
            agents=self.conflict.agents,
        )

        # Get agent outputs from bus
        agent_outputs = {}
        for resp in self.bus.get_responses():
            if resp.sender in self.conflict.agents:
                agent_outputs[resp.sender] = resp.payload.get("output", "")[:2000]

        for round_num in range(1, self.MAX_ROUNDS + 1):
            round_positions = self._run_round(round_num, agent_outputs)
            self._positions.append(round_positions)

            # Check for consensus
            consensus = self._check_consensus(round_positions)
            if consensus:
                db.complete_negotiation(
                    self._session_id,
                    consensus_reached=True,
                    final_position=consensus.position,
                )
                return consensus

        # No consensus after max rounds — highest confidence wins
        return self._resolve_no_consensus()

    def run_with_events(self):
        """Execute negotiation yielding (event_type, event_data) tuples."""
        if not self.client:
            yield ("negotiation_result", {
                "consensus_reached": False,
                "position": "Negotiation skipped",
                "confidence": 0.5,
                "dissenting_views": [],
                "rounds_taken": 0,
            })
            return

        self._session_id = db.create_negotiation_session(
            conversation_id=self.conversation_id,
            topic=self.conflict.topic,
            agents=self.conflict.agents,
        )

        agent_outputs = {}
        for resp in self.bus.get_responses():
            if resp.sender in self.conflict.agents:
                agent_outputs[resp.sender] = resp.payload.get("output", "")[:2000]

        for round_num in range(1, self.MAX_ROUNDS + 1):
            round_positions = self._run_round(round_num, agent_outputs)
            self._positions.append(round_positions)

            # Emit round events
            for pos in round_positions:
                yield ("negotiation_round", {
                    "round": round_num,
                    "agent": pos.agent_name,
                    "response_type": pos.response_type,
                    "position": pos.position[:500],
                    "confidence": pos.confidence,
                })

            consensus = self._check_consensus(round_positions)
            if consensus:
                db.complete_negotiation(
                    self._session_id,
                    consensus_reached=True,
                    final_position=consensus.position,
                )
                yield ("negotiation_result", {
                    "consensus_reached": consensus.reached,
                    "position": consensus.position,
                    "confidence": consensus.confidence,
                    "dissenting_views": consensus.dissenting_views,
                    "rounds_taken": consensus.rounds_taken,
                })
                return

        result = self._resolve_no_consensus()
        yield ("negotiation_result", {
            "consensus_reached": result.reached,
            "position": result.position,
            "confidence": result.confidence,
            "dissenting_views": result.dissenting_views,
            "rounds_taken": result.rounds_taken,
        })

    def _run_round(self, round_num: int, agent_outputs: dict[str, str]) -> list[AgentPosition]:
        """Run one round of negotiation, getting each agent's position."""
        positions = []

        for agent_name in self.conflict.agents:
            output = agent_outputs.get(agent_name, "")
            position = self._get_agent_position(agent_name, output, round_num)
            positions.append(position)

            # Persist round to DB
            if self._session_id:
                db.add_negotiation_round(
                    session_id=self._session_id,
                    round_number=round_num,
                    agent_name=agent_name,
                    response_type=position.response_type,
                    position=position.position,
                    evidence=position.evidence,
                    confidence=position.confidence,
                )

        return positions

    def _get_agent_position(self, agent_name: str, output: str, round_num: int) -> AgentPosition:
        """Ask the LLM to formulate an agent's position for the debate."""
        round_labels = {1: "Opening", 2: "Rebuttal", 3: "Final Position"}
        round_label = round_labels.get(round_num, "Position")

        # Build context from previous rounds
        prev_context = ""
        for prev_round_num, prev_positions in enumerate(self._positions, 1):
            for pos in prev_positions:
                if pos.agent_name != agent_name:
                    prev_context += f"\nRound {prev_round_num} - {pos.agent_name}: [{pos.response_type}] {pos.position[:300]}"

        prompt = f"""You are the {agent_name} agent in a structured debate about: {self.conflict.details}

Your analysis output was:
{output[:1500]}

{f"Previous debate positions:{prev_context}" if prev_context else ""}

This is Round {round_num} ({round_label}).
{"State your position, provide evidence, and assign a confidence score." if round_num == 1 else ""}
{"You may CONCEDE (agree with the other agent), COUNTER (provide counter-arguments), or REQUEST_DATA (ask for more information)." if round_num == 2 else ""}
{"State your FINAL position clearly." if round_num == 3 else ""}

Respond with JSON only:
{{"response_type": "position|concede|counter|request_data", "position": "your position", "evidence": "supporting evidence", "confidence": 0.0-1.0}}"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an agent in a structured debate. Respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.3,
            )
            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return AgentPosition(
                agent_name=agent_name,
                response_type=data.get("response_type", "position"),
                position=data.get("position", ""),
                evidence=data.get("evidence", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
        except Exception:
            return AgentPosition(
                agent_name=agent_name,
                response_type="position",
                position=output[:500],
                evidence="",
                confidence=0.5,
            )

    def _check_consensus(self, positions: list[AgentPosition]) -> ConsensusResult | None:
        """Check if agents have reached consensus."""
        if not positions:
            return None

        # All concede
        if all(p.response_type == "concede" for p in positions):
            # Use the non-conceding position from the previous round
            winner = max(positions, key=lambda p: p.confidence)
            return ConsensusResult(
                reached=True,
                position=winner.position,
                confidence=winner.confidence,
                rounds_taken=len(self._positions),
            )

        # Confidence convergence (within 0.15)
        confidences = [p.confidence for p in positions]
        if max(confidences) - min(confidences) <= 0.15:
            winner = max(positions, key=lambda p: p.confidence)
            return ConsensusResult(
                reached=True,
                position=winner.position,
                confidence=sum(confidences) / len(confidences),
                rounds_taken=len(self._positions),
            )

        # One agent concedes
        conceding = [p for p in positions if p.response_type == "concede"]
        non_conceding = [p for p in positions if p.response_type != "concede"]
        if len(conceding) > 0 and len(non_conceding) > 0:
            winner = max(non_conceding, key=lambda p: p.confidence)
            return ConsensusResult(
                reached=True,
                position=winner.position,
                confidence=winner.confidence,
                dissenting_views=[f"{p.agent_name} conceded: {p.position[:200]}" for p in conceding],
                rounds_taken=len(self._positions),
            )

        return None

    def _resolve_no_consensus(self) -> ConsensusResult:
        """Resolve when max rounds reached without consensus."""
        all_positions = [p for round_pos in self._positions for p in round_pos]
        if not all_positions:
            return ConsensusResult(
                reached=False,
                position="No positions recorded",
                confidence=0.5,
                rounds_taken=len(self._positions),
            )

        # Highest confidence wins
        last_round = self._positions[-1] if self._positions else all_positions
        winner = max(last_round, key=lambda p: p.confidence)
        dissenters = [p for p in last_round if p.agent_name != winner.agent_name]

        result = ConsensusResult(
            reached=False,
            position=winner.position,
            confidence=winner.confidence,
            dissenting_views=[f"{p.agent_name}: {p.position[:200]}" for p in dissenters],
            rounds_taken=len(self._positions),
        )

        if self._session_id:
            db.complete_negotiation(
                self._session_id,
                consensus_reached=False,
                final_position=winner.position,
            )

        return result
