"""Agent learning system that analyzes past traces to build experience context.

Extracts patterns from successful runs so agents can learn from their history
with each user — effective search terms, tool sequences, common outcomes.
"""

from .. import database as db


class AgentLearner:
    """Analyzes past agent traces to build expertise context for prompts."""

    def get_expertise_context(self, user_id: int, agent_name: str) -> str:
        """Analyze past successful traces and build an experience context block.

        Queries agent_traces + agent_steps for this user + agent.
        Extracts: successful tool sequences, effective parameters, past results.

        Returns a prompt block like:
        PAST EXPERIENCE WITH THIS USER:
        - search_jobs with ["remote", "Python", "backend"] → 12 results (best performing)
        - User's resume scored 72% ATS for backend roles
        """
        traces = db.get_traces(user_id, limit=20)

        # Filter to this agent's traces
        agent_traces = [t for t in traces if t.get("agent_name") == agent_name]

        if not agent_traces:
            return ""

        successful = [t for t in agent_traces if t.get("status") == "completed"]
        failed = [t for t in agent_traces if t.get("status") == "failed"]

        lines = ["PAST EXPERIENCE WITH THIS USER:"]

        # Extract tool patterns from successful runs
        tool_stats = self.get_tool_effectiveness(user_id, agent_name)
        if tool_stats:
            for tool_name, rate in sorted(tool_stats.items(), key=lambda x: -x[1]):
                lines.append(f"- {tool_name}: {rate:.0%} success rate in past runs")

        # Summarize recent successful outputs, annotated with feedback
        for trace in successful[:3]:
            output = trace.get("output", "")
            if output:
                preview = output[:200].replace("\n", " ").strip()
                steps = trace.get("total_steps", 0)
                tools = trace.get("total_tool_calls", 0)
                feedback = trace.get("feedback")
                prefix = ""
                if feedback == "positive":
                    prefix = "[User found this helpful] "
                elif feedback == "negative":
                    prefix = "[Try different approach] "
                lines.append(f"- {prefix}Previous run ({steps} steps, {tools} tool calls): {preview}")

        # Note recent failures
        if failed:
            lines.append(f"- {len(failed)} recent runs failed — consider alternative approaches")

        # Get relevant memories
        memories = db.search_memories(user_id, agent_name, limit=5)
        for mem in memories:
            lines.append(f"- [{mem['category']}] {mem['content']}")

        # Include RL model predictions if available
        try:
            from ..rl.model import ToolSelector
            selector = ToolSelector(user_id)
            if selector.load():
                lines.append("- [RL model] Personalized tool preferences are active")
        except Exception:
            pass

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def get_tool_effectiveness(self, user_id: int, agent_name: str) -> dict[str, float]:
        """Calculate tool success rates from past traces.

        Returns: {"search_jobs": 0.85, "research_company": 0.92, ...}
        """
        traces = db.get_traces(user_id, limit=20)
        agent_traces = [t for t in traces if t.get("agent_name") == agent_name]

        tool_counts: dict[str, dict[str, int]] = {}  # tool -> {success: N, total: N}

        for trace in agent_traces:
            trace_id = trace.get("id")
            if not trace_id:
                continue

            try:
                steps = db.get_trace_steps(trace_id)
            except Exception:
                continue

            for step in steps:
                tool = step.get("tool_name", "")
                if not tool:
                    continue

                if tool not in tool_counts:
                    tool_counts[tool] = {"success": 0, "total": 0}

                tool_counts[tool]["total"] += 1
                if step.get("success"):
                    tool_counts[tool]["success"] += 1

        # Calculate rates
        effectiveness = {}
        for tool, counts in tool_counts.items():
            if counts["total"] > 0:
                effectiveness[tool] = counts["success"] / counts["total"]

        return effectiveness
