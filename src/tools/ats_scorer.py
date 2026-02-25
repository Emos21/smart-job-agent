import re
from typing import Any

from .base import Tool


class ATSScorerTool(Tool):
    """Scores a resume against ATS (Applicant Tracking System) criteria.

    Most companies use ATS software to filter resumes before a human
    ever sees them. This tool evaluates a resume the way an ATS would:
    keyword matching, section completeness, formatting quality, and
    overall compatibility score.
    """

    # Sections that ATS systems expect to find
    EXPECTED_SECTIONS = [
        "summary", "objective", "experience", "education",
        "skills", "technical skills", "projects",
    ]

    # Common ATS red flags
    FORMATTING_PENALTIES = {
        "tables": r"[|┌┐└┘├┤┬┴┼─│]",
        "special_chars": r"[★●◆►▪]",
        "headers_as_caps": r"^[A-Z\s]{20,}$",
    }

    @property
    def name(self) -> str:
        return "score_ats"

    @property
    def description(self) -> str:
        return (
            "Score a resume against ATS (Applicant Tracking System) criteria. "
            "Checks keyword match rate against a job description, section "
            "completeness, formatting quality, and returns an overall ATS "
            "compatibility score with specific improvement suggestions."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "resume_text": {
                    "type": "string",
                    "description": "The full text of the resume",
                },
                "jd_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords extracted from the job description",
                },
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required skills from the job description",
                    "default": [],
                },
            },
            "required": ["resume_text", "jd_keywords"],
        }

    def _check_keyword_density(
        self, resume: str, keywords: list[str]
    ) -> dict[str, Any]:
        """Check how many JD keywords appear in the resume."""
        resume_lower = resume.lower()
        found = []
        missing = []

        for kw in keywords:
            if kw.lower() in resume_lower:
                found.append(kw)
            else:
                missing.append(kw)

        total = len(keywords)
        match_rate = round(len(found) / total * 100, 1) if total > 0 else 0

        return {
            "found_keywords": found,
            "missing_keywords": missing,
            "keyword_match_rate": match_rate,
        }

    def _check_sections(self, resume: str) -> dict[str, Any]:
        """Check which expected sections are present."""
        resume_lower = resume.lower()
        found_sections = []
        missing_sections = []

        for section in self.EXPECTED_SECTIONS:
            # Check if section header exists (with colon or on its own line)
            pattern = rf"(?:^|\n)\s*{re.escape(section)}[\s:]*(?:\n|$)"
            if re.search(pattern, resume_lower):
                found_sections.append(section)
            # Also check without strict line matching
            elif section in resume_lower:
                found_sections.append(section)
            else:
                missing_sections.append(section)

        completeness = round(
            len(found_sections) / len(self.EXPECTED_SECTIONS) * 100, 1
        )

        return {
            "found_sections": found_sections,
            "missing_sections": missing_sections,
            "section_completeness": completeness,
        }

    def _check_formatting(self, resume: str) -> dict[str, Any]:
        """Check for ATS-unfriendly formatting."""
        issues = []
        score = 100

        # Check for problematic characters
        for issue_name, pattern in self.FORMATTING_PENALTIES.items():
            if re.search(pattern, resume):
                issues.append(f"Contains {issue_name.replace('_', ' ')}")
                score -= 10

        # Check resume length
        word_count = len(resume.split())
        if word_count < 150:
            issues.append("Resume too short (under 150 words)")
            score -= 15
        elif word_count > 1000:
            issues.append("Resume too long (over 1000 words)")
            score -= 5

        # Check for contact info
        has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume))
        has_phone = bool(re.search(r"[\+]?[\d\s\-\(\)]{10,}", resume))

        if not has_email:
            issues.append("No email address found")
            score -= 10
        if not has_phone:
            issues.append("No phone number found")
            score -= 5

        # Check for action verbs (strong resume language)
        action_verbs = [
            "built", "developed", "designed", "implemented", "led",
            "created", "managed", "improved", "delivered", "launched",
            "architected", "optimized", "automated", "integrated",
        ]
        resume_lower = resume.lower()
        verbs_found = [v for v in action_verbs if v in resume_lower]

        if len(verbs_found) < 3:
            issues.append("Few action verbs — use more active language")
            score -= 10

        # Check for quantified achievements
        has_numbers = bool(re.search(r"\d+[kK+%]|\d{3,}", resume))
        if not has_numbers:
            issues.append("No quantified achievements (numbers, percentages)")
            score -= 10

        return {
            "formatting_score": max(score, 0),
            "issues": issues,
            "has_email": has_email,
            "has_phone": has_phone,
            "word_count": word_count,
            "action_verbs_found": verbs_found,
            "has_metrics": has_numbers,
        }

    def _calculate_overall_score(
        self,
        keyword_data: dict,
        section_data: dict,
        formatting_data: dict,
    ) -> int:
        """Calculate weighted overall ATS score."""
        # Weights: keywords 40%, sections 25%, formatting 35%
        keyword_score = keyword_data["keyword_match_rate"]
        section_score = section_data["section_completeness"]
        format_score = formatting_data["formatting_score"]

        overall = (
            keyword_score * 0.40
            + section_score * 0.25
            + format_score * 0.35
        )
        return round(overall)

    def execute(self, **kwargs) -> dict[str, Any]:
        resume_text = kwargs["resume_text"]
        jd_keywords = kwargs["jd_keywords"]

        keyword_data = self._check_keyword_density(resume_text, jd_keywords)
        section_data = self._check_sections(resume_text)
        formatting_data = self._check_formatting(resume_text)

        overall_score = self._calculate_overall_score(
            keyword_data, section_data, formatting_data
        )

        # Generate suggestions
        suggestions = []
        if keyword_data["missing_keywords"]:
            top_missing = keyword_data["missing_keywords"][:5]
            suggestions.append(
                f"Add these missing keywords: {', '.join(top_missing)}"
            )
        if section_data["missing_sections"]:
            suggestions.append(
                f"Add missing sections: {', '.join(section_data['missing_sections'])}"
            )
        for issue in formatting_data["issues"]:
            suggestions.append(f"Fix: {issue}")

        # Score interpretation
        if overall_score >= 80:
            grade = "STRONG"
        elif overall_score >= 60:
            grade = "MODERATE"
        elif overall_score >= 40:
            grade = "NEEDS WORK"
        else:
            grade = "HIGH RISK"

        return {
            "success": True,
            "overall_score": overall_score,
            "grade": grade,
            "keyword_analysis": keyword_data,
            "section_analysis": section_data,
            "formatting_analysis": formatting_data,
            "suggestions": suggestions,
        }
