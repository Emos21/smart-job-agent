"""Memory tools that agents can invoke mid-execution.

These tools give agents the ability to recall past memories, store new ones,
and review past work traces — all during their ReAct loop.
"""

from typing import Any

from .base import Tool
from .. import database as db
from ..episodic_memory import EpisodicMemory


class RecallMemoryTool(Tool):
    """Tool for recalling user memories during agent execution."""

    def __init__(self):
        self._user_id: int | None = None

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "recall_memory"

    @property
    def description(self) -> str:
        return (
            "Search the user's memory for relevant past information. "
            "Returns facts, preferences, goals, and outcomes from previous conversations. "
            "Use this when you need context about the user's background, preferences, or past results."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find relevant memories (e.g. 'Python skills', 'target company', 'ATS score')",
                },
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "goal", "outcome"],
                    "description": "Optional: filter by memory category",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        if not self._user_id:
            return {"success": False, "error": "No user context available"}

        query = kwargs.get("query", "")
        category = kwargs.get("category")

        if query:
            # Use EpisodicMemory.search() for semantic search when available
            memory = EpisodicMemory(self._user_id)
            memories = memory.search(query, limit=10)
        elif category:
            memories = db.get_memories(self._user_id, category=category, limit=10)
        else:
            memories = db.get_memories(self._user_id, limit=10)

        results = []
        for mem in memories:
            results.append({
                "content": mem["content"],
                "category": mem["category"],
                "created_at": mem.get("created_at", ""),
            })

        return {
            "success": True,
            "memories": results,
            "count": len(results),
        }


class StoreMemoryTool(Tool):
    """Tool for storing new memories during agent execution."""

    def __init__(self):
        self._user_id: int | None = None

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "store_memory"

    @property
    def description(self) -> str:
        return (
            "Store an important fact or observation about the user for future reference. "
            "Use this when you discover something worth remembering — skills, preferences, "
            "job search results, ATS scores, interview outcomes, etc."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact or observation to remember (be specific and concise)",
                },
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "goal", "outcome"],
                    "description": "Category: fact (objective info), preference (user likes/dislikes), goal (career targets), outcome (results of actions)",
                },
            },
            "required": ["content", "category"],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        if not self._user_id:
            return {"success": False, "error": "No user context available"}

        content = kwargs.get("content", "")
        category = kwargs.get("category", "fact")

        if not content:
            return {"success": False, "error": "Content is required"}

        valid_categories = {"fact", "preference", "goal", "outcome"}
        if category not in valid_categories:
            category = "fact"

        mem_id = db.save_memory(
            user_id=self._user_id,
            content=content,
            category=category,
        )

        return {
            "success": True,
            "memory_id": mem_id,
            "message": f"Stored {category}: {content[:100]}",
        }


class RecallTraceTool(Tool):
    """Tool for recalling past agent work traces."""

    def __init__(self):
        self._user_id: int | None = None

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "recall_past_work"

    @property
    def description(self) -> str:
        return (
            "Review summaries of past agent runs for this user. "
            "Shows what agents did previously, what tools were used, and outcomes. "
            "Useful for avoiding redundant work or building on past results."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["scout", "match", "forge", "coach"],
                    "description": "Optional: filter by agent type",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of past runs to retrieve (default 5, max 10)",
                },
            },
            "required": [],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        if not self._user_id:
            return {"success": False, "error": "No user context available"}

        agent_name = kwargs.get("agent_name")
        limit = min(kwargs.get("limit", 5), 10)

        traces = db.get_traces(self._user_id, limit=20)

        # Filter by agent if specified
        if agent_name:
            traces = [t for t in traces if t.get("agent_name") == agent_name]

        traces = traces[:limit]

        results = []
        for trace in traces:
            results.append({
                "agent": trace.get("agent_name", ""),
                "intent": trace.get("intent", ""),
                "status": trace.get("status", ""),
                "output_preview": (trace.get("output") or "")[:500],
                "total_steps": trace.get("total_steps", 0),
                "total_tool_calls": trace.get("total_tool_calls", 0),
                "started_at": trace.get("started_at", ""),
            })

        return {
            "success": True,
            "traces": results,
            "count": len(results),
        }
