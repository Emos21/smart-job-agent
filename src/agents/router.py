"""Smart intent classifier that routes user messages to specialized agents.

Instead of a dumb tool loop, the router classifies user intent and dispatches
to the right agent(s) — Scout, Match, Forge, Coach, or combinations.
"""

import json
import os
from dataclasses import dataclass, field

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

ROUTING_PROMPT = """You are an intent classifier for KaziAI, a career assistant.
Classify the user's message into exactly one intent and determine which agents to invoke.

INTENTS:
- job_search: User wants to find, search for, or discover jobs/roles/positions
- analyze_match: User wants to compare resume vs job description, check fit, or get ATS score
- write_materials: User wants a cover letter, resume rewrite, or application materials written
- interview_prep: User wants interview preparation, practice questions, or coaching
- multi_step: User wants end-to-end help (e.g. "help me apply to X" or "help me land a role at Y")
- general_chat: Greetings, general career advice, casual conversation, or anything that doesn't need a specialized agent

AGENTS:
- scout: Job discovery and company research
- match: Skills analysis, JD parsing, and ATS scoring
- forge: Cover letter and resume writing
- coach: Interview preparation and coaching

ROUTING RULES:
- job_search → ["scout"]
- analyze_match → ["match"]
- write_materials → ["match", "forge"] (match first for context, then forge writes)
- interview_prep → ["coach"]
- multi_step → ["scout", "match", "forge", "coach"] (or a relevant subset)
- general_chat → [] (no agents needed)

CONTEXT EXTRACTION:
Extract any mentioned: company name, role/title, skills, URL, or job description text.

Respond with ONLY valid JSON (no markdown, no explanation):
{
  "intent": "one of the intents above",
  "agents": ["list", "of", "agent", "names"],
  "extracted_context": {
    "company": "company name or null",
    "role": "role/title or null",
    "skills": ["mentioned", "skills"] or [],
    "url": "any URL mentioned or null",
    "has_jd": true/false
  },
  "reasoning": "one sentence explaining why this classification",
  "needs_resume": true/false,
  "needs_profile": true/false
}"""


@dataclass
class RoutingDecision:
    """Result of classifying a user message into an intent + agent pipeline."""
    intent: str
    agents: list[str]
    extracted_context: dict
    reasoning: str
    needs_resume: bool = False
    needs_profile: bool = False


class AgentRouter:
    """Classifies user intent and determines which agents to dispatch."""

    VALID_INTENTS = {
        "job_search", "analyze_match", "write_materials",
        "interview_prep", "multi_step", "general_chat",
    }
    VALID_AGENTS = {"scout", "match", "forge", "coach"}

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY")
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        return self._client

    def route(self, message: str, has_resume: bool = False, has_profile: bool = False) -> RoutingDecision:
        """Classify user intent with a cheap, focused LLM call."""
        context_hint = ""
        if has_resume:
            context_hint += " The user has a resume on file."
        if has_profile:
            context_hint += " The user has a profile set up."

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": ROUTING_PROMPT},
                    {"role": "user", "content": f"{message}{context_hint}"},
                ],
                max_tokens=300,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or "{}"
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return self._parse_response(data)

        except Exception:
            # On any failure, fall back to general chat
            return RoutingDecision(
                intent="general_chat",
                agents=[],
                extracted_context={},
                reasoning="Router fallback due to classification error",
            )

    def _parse_response(self, data: dict) -> RoutingDecision:
        """Validate and normalize the LLM's routing response."""
        intent = data.get("intent", "general_chat")
        if intent not in self.VALID_INTENTS:
            intent = "general_chat"

        agents = [a for a in data.get("agents", []) if a in self.VALID_AGENTS]

        # Ensure intent-agent consistency
        if intent == "general_chat":
            agents = []
        elif not agents:
            # If intent suggests agents but none were returned, apply defaults
            defaults = {
                "job_search": ["scout"],
                "analyze_match": ["match"],
                "write_materials": ["match", "forge"],
                "interview_prep": ["coach"],
                "multi_step": ["scout", "match", "forge", "coach"],
            }
            agents = defaults.get(intent, [])

        return RoutingDecision(
            intent=intent,
            agents=agents,
            extracted_context=data.get("extracted_context", {}),
            reasoning=data.get("reasoning", ""),
            needs_resume=bool(data.get("needs_resume", False)),
            needs_profile=bool(data.get("needs_profile", False)),
        )
