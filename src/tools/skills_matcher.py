from typing import Any

from .base import Tool


class SkillsMatcherTool(Tool):
    """Compares skills between a job description and a resume.

    Takes two lists of skills and produces a match analysis:
    which skills overlap, which are missing, and an overall
    match percentage. Handles variations in skill naming
    (e.g., 'JS' matches 'JavaScript').
    """

    # Common aliases so "JS" matches "JavaScript", etc.
    SKILL_ALIASES = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "postgres": "postgresql",
        "k8s": "kubernetes",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "react.js": "react",
        "node.js": "node",
        "nodejs": "node",
        "nextjs": "next.js",
        "fastapi": "fastapi",
        "aws": "amazon web services",
        "gcp": "google cloud platform",
        "ci/cd": "ci cd",
    }

    @property
    def name(self) -> str:
        return "match_skills"

    @property
    def description(self) -> str:
        return (
            "Compare required skills from a job description against skills "
            "found in a resume. Returns matched skills, missing skills, "
            "and a match score."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills required by the job description",
                },
                "candidate_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills the candidate has from their resume",
                },
                "preferred_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nice-to-have skills from the job description",
                    "default": [],
                },
            },
            "required": ["required_skills", "candidate_skills"],
        }

    def _normalize(self, skill: str) -> str:
        """Normalize a skill name for comparison."""
        lowered = skill.lower().strip()
        return self.SKILL_ALIASES.get(lowered, lowered)

    def _find_match(self, skill: str, skill_set: set[str]) -> bool:
        """Check if a skill matches any skill in the set, accounting for
        partial matches (e.g., 'python' matches 'python 3')."""
        normalized = self._normalize(skill)
        for candidate in skill_set:
            candidate_norm = self._normalize(candidate)
            if normalized == candidate_norm:
                return True
            if normalized in candidate_norm or candidate_norm in normalized:
                return True
        return False

    def execute(self, **kwargs) -> dict[str, Any]:
        required = kwargs["required_skills"]
        candidate = kwargs["candidate_skills"]
        preferred = kwargs.get("preferred_skills", [])

        candidate_set = set(candidate)

        matched_required = []
        missing_required = []
        for skill in required:
            if self._find_match(skill, candidate_set):
                matched_required.append(skill)
            else:
                missing_required.append(skill)

        matched_preferred = []
        missing_preferred = []
        for skill in preferred:
            if self._find_match(skill, candidate_set):
                matched_preferred.append(skill)
            else:
                missing_preferred.append(skill)

        total = len(required) + len(preferred)
        matched_total = len(matched_required) + len(matched_preferred)
        match_score = round(matched_total / total * 100, 1) if total > 0 else 0

        # Weight required skills more heavily
        required_score = (
            round(len(matched_required) / len(required) * 100, 1)
            if required
            else 0
        )

        return {
            "success": True,
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_preferred": matched_preferred,
            "missing_preferred": missing_preferred,
            "required_match_pct": required_score,
            "overall_match_pct": match_score,
        }
