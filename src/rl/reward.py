"""Reward computation from agent traces and user feedback.

Maps feedback signals to numeric rewards for the RL model.
"""


def compute_reward(trace: dict) -> float | None:
    """Compute a reward signal from a completed agent trace.

    Returns:
        float: reward value (-1.0 to 1.0), or None if no signal.
    """
    feedback = trace.get("feedback")
    status = trace.get("status", "")

    # Explicit user feedback is strongest signal
    if feedback == "positive":
        return 1.0
    if feedback == "negative":
        return -1.0

    # Agent completion signals
    if status == "completed":
        # Moderate positive — agent finished successfully
        tool_calls = trace.get("total_tool_calls", 0)
        steps = trace.get("total_steps", 0)

        # Efficient completion bonus
        if steps > 0 and tool_calls <= steps:
            return 0.5
        return 0.3

    if status == "failed":
        return -0.5

    if status == "cancelled":
        # User cancelled — mild negative signal
        return -0.3

    if status == "max_steps":
        # Hit step limit — inefficient but not failure
        return -0.2

    # No signal
    return None
