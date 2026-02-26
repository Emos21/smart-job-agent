"""RL trainer that pulls traces, computes rewards, and updates per-user models."""

from .. import database as db
from .features import extract_features, TOOLS
from .model import ToolSelector
from .reward import compute_reward


class RLTrainer:
    """Trains per-user RL models from agent trace history."""

    def train_batch(self, user_id: int) -> dict:
        """Pull recent traces with feedback, compute rewards, update model.

        Returns training stats dict.
        """
        selector = ToolSelector(user_id)
        selector.load()

        profile = db.get_profile(user_id)
        traces = db.get_traces(user_id, limit=50)

        samples_trained = 0
        for trace in traces:
            reward = compute_reward(trace)
            if reward is None:
                continue

            agent_name = trace.get("agent_name", "")
            task = trace.get("task", "")
            trace_id = trace.get("id")
            if not trace_id:
                continue

            # Get tool calls from trace steps
            try:
                steps = db.get_trace_steps(trace_id)
            except Exception:
                continue

            for step in steps:
                tool_name = step.get("tool_name", "")
                if not tool_name or tool_name not in TOOLS:
                    continue

                features = extract_features(profile, task, agent_name, tool_name)
                selector.update(features, tool_name, reward)
                samples_trained += 1

        if samples_trained > 0:
            selector.save()

            # Log training run
            try:
                db.log_rl_training(user_id, samples_trained)
            except Exception:
                pass

        return {
            "user_id": user_id,
            "samples_trained": samples_trained,
        }

    def get_tool_hints(self, user_id: int, context: dict) -> str:
        """Generate tool preference hints for agent prompts.

        Args:
            context: {"query": str, "agent_name": str, "profile": dict}

        Returns a string like "Based on past outcomes, prefer: search_jobs, research_company"
        """
        selector = ToolSelector(user_id)
        if not selector.load():
            return ""

        query = context.get("query", "")
        agent_name = context.get("agent_name", "")
        profile = context.get("profile")

        # Get predictions for each tool
        predictions = {}
        for tool_name in TOOLS:
            features = extract_features(profile, query, agent_name, tool_name)
            probs = selector.predict(features)
            predictions[tool_name] = probs.get(tool_name, 0.0)

        # Get top tools above threshold
        sorted_tools = sorted(predictions.items(), key=lambda x: -x[1])
        top_tools = [(name, score) for name, score in sorted_tools if score > 0.1][:5]

        if not top_tools:
            return ""

        tool_list = ", ".join(f"{name} ({score:.0%})" for name, score in top_tools)
        return f"Based on past outcomes, prefer: {tool_list}"
