from typing import Any

from .base import Tool


class InterviewPrepTool(Tool):
    """Generates likely interview questions based on a job description.

    Analyzes the role requirements, company context, and candidate
    background to produce targeted questions the interviewer is
    likely to ask — grouped by category (technical, behavioral,
    situational, role-specific).
    """

    # Question templates by category
    TECHNICAL_TEMPLATES = [
        "Describe your experience with {skill}. What's the most complex project you've used it on?",
        "How would you approach building {responsibility}?",
        "What's the difference between {skill} and alternatives you've used?",
        "Walk me through how you'd debug a production issue in a {skill} system.",
        "How do you ensure code quality and testing in {skill} projects?",
    ]

    BEHAVIORAL_TEMPLATES = [
        "Tell me about a time you had to deliver under a tight deadline.",
        "Describe a situation where you disagreed with a technical decision. How did you handle it?",
        "Give an example of a project that failed or had major setbacks. What did you learn?",
        "How do you prioritize when you have multiple competing deadlines?",
        "Tell me about a time you had to learn a new technology quickly.",
    ]

    SITUATIONAL_TEMPLATES = [
        "If you joined and found the codebase had no tests, what would you do?",
        "How would you handle a situation where a stakeholder keeps changing requirements?",
        "If you discovered a critical security vulnerability the day before launch, what would you do?",
        "How would you onboard yourself in the first 30 days at {company}?",
    ]

    @property
    def name(self) -> str:
        return "prepare_interview"

    @property
    def description(self) -> str:
        return (
            "Generate interview preparation questions and talking points. "
            "Use when user asks for help preparing for an interview, wants "
            "practice questions, or mentions an upcoming interview. "
            "Produces technical, behavioral, and situational questions."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "role_title": {
                    "type": "string",
                    "description": "The job title",
                },
                "company_name": {
                    "type": "string",
                    "description": "The company name",
                },
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required skills from the JD",
                },
                "responsibilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key responsibilities from the JD",
                },
                "candidate_experiences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Candidate's key experiences from resume",
                },
            },
            "required": [
                "role_title",
                "company_name",
                "required_skills",
                "responsibilities",
            ],
        }

    def _generate_technical_questions(
        self, skills: list[str], responsibilities: list[str]
    ) -> list[dict]:
        """Generate technical questions from skills and responsibilities."""
        questions = []

        for skill in skills[:5]:
            questions.append({
                "question": f"Describe your experience with {skill}. What's the most complex project you've used it on?",
                "category": "technical",
                "focus": skill,
            })

        for resp in responsibilities[:3]:
            questions.append({
                "question": f"How would you approach: {resp}?",
                "category": "technical",
                "focus": resp,
            })

        return questions

    def _generate_behavioral_questions(self) -> list[dict]:
        """Generate standard behavioral interview questions."""
        return [
            {"question": q, "category": "behavioral", "focus": "soft skills"}
            for q in self.BEHAVIORAL_TEMPLATES
        ]

    def _generate_situational_questions(
        self, company: str
    ) -> list[dict]:
        """Generate situational questions."""
        return [
            {
                "question": q.format(company=company),
                "category": "situational",
                "focus": "problem solving",
            }
            for q in self.SITUATIONAL_TEMPLATES
        ]

    def _generate_role_questions(
        self, role: str, company: str
    ) -> list[dict]:
        """Generate role-specific questions."""
        return [
            {
                "question": f"Why are you interested in the {role} role at {company}?",
                "category": "role-specific",
                "focus": "motivation",
            },
            {
                "question": f"What do you know about {company} and our mission?",
                "category": "role-specific",
                "focus": "research",
            },
            {
                "question": "Where do you see yourself in 2-3 years?",
                "category": "role-specific",
                "focus": "growth",
            },
            {
                "question": "What's your expected compensation?",
                "category": "role-specific",
                "focus": "negotiation",
            },
        ]

    def _suggest_talking_points(
        self, question: dict, experiences: list[str]
    ) -> list[str]:
        """Suggest relevant talking points for a question."""
        points = []
        q_lower = question["question"].lower()

        for exp in experiences:
            exp_lower = exp.lower()
            # If experience seems relevant to the question topic
            focus = question.get("focus", "").lower()
            if focus and any(
                word in exp_lower
                for word in focus.split()
                if len(word) > 3
            ):
                points.append(f"Reference: {exp}")

        if not points:
            points.append("Prepare a specific example from your experience")

        return points[:2]

    def execute(self, **kwargs) -> dict[str, Any]:
        role = kwargs["role_title"]
        company = kwargs["company_name"]
        skills = kwargs["required_skills"]
        responsibilities = kwargs["responsibilities"]
        experiences = kwargs.get("candidate_experiences", [])

        all_questions = []
        all_questions.extend(
            self._generate_technical_questions(skills, responsibilities)
        )
        all_questions.extend(self._generate_behavioral_questions())
        all_questions.extend(self._generate_situational_questions(company))
        all_questions.extend(self._generate_role_questions(role, company))

        # Add talking points
        for q in all_questions:
            q["talking_points"] = self._suggest_talking_points(q, experiences)

        # Group by category
        by_category = {}
        for q in all_questions:
            cat = q["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(q)

        return {
            "success": True,
            "total_questions": len(all_questions),
            "questions_by_category": by_category,
            "all_questions": all_questions,
        }
