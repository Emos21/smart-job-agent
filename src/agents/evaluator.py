"""Pipeline evaluator that decides the next action after each agent runs.

Runs a cheap LLM call to analyze agent output quality and decide:
continue, loop_back, skip_next, stop, or add_agent.
"""

import json
import os
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

EVAL_PROMPT = """You are a pipeline evaluator for a career AI system. After an agent produces output, decide what should happen next.

AGENTS: scout (job search), match (resume analysis), forge (resume/cover letter writing), coach (interview prep)

DECISION OPTIONS:
- "continue": The output is good, proceed to the next agent in the pipeline.
- "loop_back": Output is poor or missing critical data. Re-run the same or a different agent.
- "skip_next": Output is so strong the next agent is unnecessary.
- "stop": All work is done; no more agents needed.
- "add_agent": Insert an additional agent that wasn't originally planned.

GUIDELINES:
- If search found 0 results → loop_back to scout with broader terms
- If ATS score is above 90% → skip_next (forge is unnecessary)
- If agent output is clearly wrong (wrong company, irrelevant data) → loop_back
- If user only asked for one thing and it's done → stop
- Default to "continue" if unsure
- Be concise in your reason (one sentence max)

Respond with ONLY valid JSON (no markdown):
{"action": "continue|loop_back|skip_next|stop|add_agent", "reason": "brief explanation", "target_agent": "agent name or empty string"}"""


@dataclass
class EvalDecision:
    """Result of the evaluator analyzing an agent's output."""
    action: str        # "continue", "loop_back", "skip_next", "stop", "add_agent"
    reason: str
    target_agent: str  # for loop_back or add_agent


class PipelineEvaluator:
    """Lightweight evaluator that runs after each agent to control pipeline flow."""

    VALID_ACTIONS = {"continue", "loop_back", "skip_next", "stop", "add_agent", "negotiate"}
    VALID_AGENTS = {"scout", "match", "forge", "coach"}

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            provider = os.getenv("LLM_PROVIDER", "groq")
            if provider == "ollama":
                self._client = OpenAI(
                    api_key="ollama",
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                )
            else:
                api_key = os.getenv("GROQ_API_KEY")
                if api_key:
                    self._client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.groq.com/openai/v1",
                    )
        return self._client

    def evaluate(self, agent_result, message_bus, remaining_agents, routing) -> EvalDecision:
        """Analyze agent output and decide what happens next.

        Uses a cheap, fast LLM call (max_tokens=200) to make the decision.
        Falls back to 'continue' on any error.
        """
        if not self.client:
            return EvalDecision(action="continue", reason="No LLM client", target_agent="")

        # Build concise context for the evaluator
        remaining_str = ", ".join(remaining_agents) if remaining_agents else "none"
        output_preview = agent_result.output[:1500] if agent_result.output else "(empty)"

        user_msg = (
            f"Agent: {agent_result.agent_name}\n"
            f"Intent: {routing.intent}\n"
            f"Remaining agents: {remaining_str}\n"
            f"Agent output (preview):\n{output_preview}"
        )

        try:
            response = self.client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": EVAL_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=200,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return self._parse_decision(data)

        except Exception:
            return EvalDecision(action="continue", reason="Evaluator fallback", target_agent="")

    def _parse_decision(self, data: dict) -> EvalDecision:
        """Validate and normalize the evaluator's decision."""
        action = data.get("action", "continue")
        if action not in self.VALID_ACTIONS:
            action = "continue"

        reason = str(data.get("reason", ""))[:200]

        target = data.get("target_agent", "")
        if target and target not in self.VALID_AGENTS:
            target = ""

        # Safety: loop_back and add_agent require a target
        if action in ("loop_back", "add_agent") and not target:
            action = "continue"
            reason = reason or "No target agent specified, continuing"

        return EvalDecision(action=action, reason=reason, target_agent=target)
