"""Episodic memory system for KaziAI.

Stores and retrieves facts the AI learned about a user across sessions.
Categories: fact, preference, goal, outcome.
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from . import database as db
from . import embeddings

load_dotenv()


class EpisodicMemory:
    """Manages persistent memories about a specific user."""

    VALID_CATEGORIES = {"fact", "preference", "goal", "outcome"}

    def __init__(self, user_id: int):
        self.user_id = user_id

    def remember(self, content: str, category: str = "fact", conversation_id: int | None = None) -> int:
        """Store a fact about the user, with optional embedding for semantic search."""
        if category not in self.VALID_CATEGORIES:
            category = "fact"

        embedding_json = None
        if embeddings.is_available():
            vec = embeddings.get_embedding(content)
            if vec:
                embedding_json = json.dumps(vec)

        return db.save_memory(
            user_id=self.user_id,
            content=content,
            category=category,
            source_conversation_id=conversation_id,
            embedding=embedding_json,
        )

    def recall(self, category: str | None = None, limit: int = 20) -> list[dict]:
        """Retrieve memories, optionally filtered by category."""
        return db.get_memories(self.user_id, category=category, limit=limit)

    def recall_as_context(self, limit: int = 10) -> str:
        """Build a text block of memories for prompt injection."""
        memories = db.get_memories(self.user_id, limit=limit)
        if not memories:
            return ""

        lines = ["PREVIOUS KNOWLEDGE ABOUT THIS USER:"]
        for mem in memories:
            lines.append(f"- [{mem['category']}] {mem['content']}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories — semantic first (if available), falling back to keyword LIKE."""
        if embeddings.is_available():
            query_vec = embeddings.get_embedding(query)
            if query_vec:
                results = db.semantic_search_memories(self.user_id, query_vec, limit=limit)
                if results:
                    return results
        # Fallback to keyword search
        return db.search_memories(self.user_id, query, limit=limit)


MEMORY_EXTRACTION_PROMPT = """You are a memory extraction system. Given the output of an AI agent that helped a user, extract key facts worth remembering about the user for future conversations.

Extract up to 5 facts. Each fact should be a concise statement. Categorize each as:
- "fact": objective information (skills, experience, education, current job)
- "preference": user preferences (remote work, specific companies, salary expectations)
- "goal": career goals or targets
- "outcome": results of actions taken (ATS scores, interview prep completed, applications sent)

Respond with ONLY valid JSON array (no markdown):
[{"content": "fact text", "category": "fact|preference|goal|outcome"}]

If there are no meaningful facts to extract, return: []"""


def extract_memories_from_output(agent_output: str, user_message: str = "") -> list[dict]:
    """Use a cheap LLM call to extract memorable facts from agent output."""
    provider = os.getenv("LLM_PROVIDER", "groq")
    if provider == "ollama":
        client = OpenAI(
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return []
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
                {"role": "user", "content": f"User said: {user_message[:500]}\n\nAgent output:\n{agent_output[:2000]}"},
            ],
            max_tokens=400,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "[]"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return []

        valid = []
        for f in facts[:5]:
            if isinstance(f, dict) and "content" in f:
                cat = f.get("category", "fact")
                if cat not in EpisodicMemory.VALID_CATEGORIES:
                    cat = "fact"
                valid.append({"content": f["content"], "category": cat})
        return valid

    except Exception:
        return []
