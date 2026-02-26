"""Embedding utilities for semantic memory search.

Uses OpenAI text-embedding-3-small when OPENAI_API_KEY is available.
Falls back gracefully — all functions return None or empty when unavailable.
"""

import json
import math
import os

from dotenv import load_dotenv

load_dotenv()


def is_available() -> bool:
    """Check if embedding generation is available (requires OPENAI_API_KEY)."""
    return bool(os.getenv("OPENAI_API_KEY"))


def get_embedding(text: str) -> list[float] | None:
    """Generate an embedding vector for the given text.

    Returns None if OPENAI_API_KEY is not set or on any error.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],  # model limit safety
        )
        return response.data[0].embedding
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Pure Python, no numpy."""
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def backfill_embeddings(user_id: int) -> int:
    """Embed existing memories that lack embeddings.

    Returns the number of memories backfilled.
    """
    if not is_available():
        return 0

    from . import database as db

    memories = db.get_all_memories_with_embeddings(user_id)
    count = 0

    for mem in memories:
        if mem.get("embedding"):
            continue  # already has embedding

        embedding = get_embedding(mem["content"])
        if embedding:
            conn = db.get_db()
            conn.execute(
                "UPDATE user_memories SET embedding = ? WHERE id = ?",
                (json.dumps(embedding), mem["id"]),
            )
            conn.commit()
            conn.close()
            count += 1

    return count
