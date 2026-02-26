"""Feature extraction for the contextual bandit RL model.

Converts user profile, query, agent, and tool into a fixed-size numeric vector.
"""

INDUSTRIES = [
    "tech", "finance", "healthcare", "education", "retail",
    "manufacturing", "consulting", "government", "nonprofit", "other",
]

EXPERIENCE_LEVELS = ["entry-level", "mid-level", "senior", "staff/principal", "executive"]

AGENTS = ["scout", "match", "forge", "coach"]

TOOLS = [
    "search_jobs", "parse_job_description", "analyze_resume",
    "match_skills", "score_ats", "prepare_interview",
    "generate_cover_letter", "rewrite_resume", "research_company",
    "analyze_github", "research_salary", "draft_email",
    "generate_learning_path", "mock_interview", "fetch_url",
]

# Total: 10 (industry) + 5 (experience) + 3 (query) + 4 (agent) + 15 (tool) = 37
FEATURE_DIM = len(INDUSTRIES) + len(EXPERIENCE_LEVELS) + 3 + len(AGENTS) + len(TOOLS)


def _one_hot(value: str, options: list[str]) -> list[float]:
    """Create a one-hot vector for a categorical value."""
    vec = [0.0] * len(options)
    lower = value.lower().strip()
    for i, opt in enumerate(options):
        if opt in lower or lower in opt:
            vec[i] = 1.0
            break
    return vec


def extract_features(
    user_profile: dict | None,
    query: str,
    agent_name: str,
    tool_name: str,
) -> list[float]:
    """Extract a numeric feature vector for the RL model.

    Returns a list of floats with length FEATURE_DIM.
    """
    features: list[float] = []
    profile = user_profile or {}

    # Industry one-hot (10)
    bio = (profile.get("bio") or "") + " " + (profile.get("target_role") or "")
    industry = "other"
    for ind in INDUSTRIES:
        if ind in bio.lower():
            industry = ind
            break
    features.extend(_one_hot(industry, INDUSTRIES))

    # Experience level one-hot (5)
    exp = profile.get("experience_level") or ""
    features.extend(_one_hot(exp, EXPERIENCE_LEVELS))

    # Query features (3)
    features.append(min(len(query) / 500.0, 1.0))  # normalized length
    features.append(1.0 if "?" in query else 0.0)  # is question
    goals_count = len(profile.get("skills") or [])
    features.append(min(goals_count / 20.0, 1.0))  # skill count proxy

    # Agent one-hot (4)
    features.extend(_one_hot(agent_name, AGENTS))

    # Tool one-hot (15)
    features.extend(_one_hot(tool_name, TOOLS))

    return features
