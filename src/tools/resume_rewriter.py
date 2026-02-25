from typing import Any

from .base import Tool


class ResumeRewriterTool(Tool):
    """Restructures resume bullet points to align with a job description.

    Takes existing resume content and JD requirements, then produces
    rewritten bullet points that use the JD's language and emphasize
    the most relevant experiences. Does not fabricate — only reframes
    existing experience.
    """

    @property
    def name(self) -> str:
        return "rewrite_resume"

    @property
    def description(self) -> str:
        return (
            "Rewrite resume bullet points to better match a job description. "
            "Takes the candidate's experience and the target JD keywords, "
            "then produces reframed bullets that emphasize relevant skills "
            "and use the JD's language. Does not fabricate experience."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "experience_bullets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Original resume bullet points to rewrite",
                },
                "target_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords from the target job description",
                },
                "role_title": {
                    "type": "string",
                    "description": "The job title being applied for",
                },
                "candidate_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills the candidate actually has",
                },
            },
            "required": [
                "experience_bullets",
                "target_keywords",
                "role_title",
                "candidate_skills",
            ],
        }

    def _find_relevant_keywords(
        self, bullet: str, keywords: list[str]
    ) -> list[str]:
        """Find which target keywords could apply to this bullet."""
        bullet_lower = bullet.lower()
        relevant = []
        for kw in keywords:
            kw_lower = kw.lower()
            # Direct match
            if kw_lower in bullet_lower:
                relevant.append(kw)
                continue
            # Partial/related matches
            words = kw_lower.split()
            if any(w in bullet_lower for w in words if len(w) > 3):
                relevant.append(kw)
        return relevant

    def _suggest_reframe(
        self,
        bullet: str,
        relevant_keywords: list[str],
        all_keywords: list[str],
        skills: list[str],
    ) -> dict[str, Any]:
        """Produce a reframing suggestion for a single bullet."""
        suggestions = []

        # Suggest adding relevant keywords that aren't already present
        bullet_lower = bullet.lower()
        keywords_to_add = [
            kw for kw in relevant_keywords
            if kw.lower() not in bullet_lower
        ]

        if keywords_to_add:
            suggestions.append(
                f"Incorporate keywords: {', '.join(keywords_to_add)}"
            )

        # Check for weak language
        weak_phrases = [
            "responsible for", "helped with", "worked on",
            "assisted in", "involved in", "participated in",
        ]
        for phrase in weak_phrases:
            if phrase in bullet_lower:
                suggestions.append(
                    f"Replace '{phrase}' with a strong action verb "
                    f"(built, designed, implemented, led, optimized)"
                )

        # Check for missing metrics
        import re
        has_numbers = bool(re.search(r"\d", bullet))
        if not has_numbers:
            suggestions.append(
                "Add quantified impact (e.g., 'processing 100k+ records', "
                "'reduced load time by 40%')"
            )

        return {
            "original": bullet,
            "relevant_keywords": relevant_keywords,
            "suggestions": suggestions,
            "keywords_to_incorporate": keywords_to_add,
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        bullets = kwargs["experience_bullets"]
        keywords = kwargs["target_keywords"]
        role = kwargs["role_title"]
        skills = kwargs["candidate_skills"]

        rewritten = []
        for bullet in bullets:
            relevant = self._find_relevant_keywords(bullet, keywords)
            result = self._suggest_reframe(bullet, relevant, keywords, skills)
            rewritten.append(result)

        # Identify keywords not covered by any bullet
        all_covered = set()
        for item in rewritten:
            all_covered.update(kw.lower() for kw in item["relevant_keywords"])

        uncovered_keywords = [
            kw for kw in keywords
            if kw.lower() not in all_covered
        ]

        return {
            "success": True,
            "target_role": role,
            "rewritten_bullets": rewritten,
            "uncovered_keywords": uncovered_keywords,
            "coverage_rate": round(
                (len(keywords) - len(uncovered_keywords))
                / len(keywords) * 100, 1
            ) if keywords else 0,
        }
