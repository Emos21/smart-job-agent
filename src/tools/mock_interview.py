from typing import Any

from .base import Tool


class MockInterviewTool(Tool):
    """Conducts a mock interview session by generating questions and evaluating answers.

    Generates role-specific interview questions and, when provided with
    the candidate's answer, evaluates it using the STAR method framework
    and provides actionable feedback.
    """

    STAR_CRITERIA = {
        "situation": "Did the answer describe a specific situation or context?",
        "task": "Did the answer explain the specific task or challenge?",
        "action": "Did the answer detail the specific actions taken?",
        "result": "Did the answer include measurable results or outcomes?",
    }

    @property
    def name(self) -> str:
        return "mock_interview"

    @property
    def description(self) -> str:
        return (
            "Conduct a mock interview session. Can generate interview questions "
            "for a specific role, or evaluate a candidate's answer to a question "
            "using the STAR method and provide detailed feedback with suggestions."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Mode: 'generate_question' to get a new question, 'evaluate_answer' to critique an answer",
                    "enum": ["generate_question", "evaluate_answer"],
                },
                "role_title": {
                    "type": "string",
                    "description": "The job title for the mock interview",
                },
                "question_type": {
                    "type": "string",
                    "description": "Type of question: 'technical', 'behavioral', 'situational', 'system_design'",
                    "default": "behavioral",
                },
                "difficulty": {
                    "type": "string",
                    "description": "Difficulty level: 'easy', 'medium', 'hard'",
                    "default": "medium",
                },
                "question": {
                    "type": "string",
                    "description": "The interview question (required for evaluate_answer mode)",
                    "default": "",
                },
                "answer": {
                    "type": "string",
                    "description": "The candidate's answer to evaluate (required for evaluate_answer mode)",
                    "default": "",
                },
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills required for the role (for question generation)",
                    "default": [],
                },
            },
            "required": ["mode", "role_title"],
        }

    def _generate_question(
        self, role: str, q_type: str, difficulty: str, skills: list[str]
    ) -> dict[str, Any]:
        """Generate a single interview question."""
        questions = {
            "behavioral": {
                "easy": [
                    "Tell me about a project you're proud of. What was your role and what did you accomplish?",
                    "Describe a time you had to learn something new quickly. How did you approach it?",
                    "Tell me about a time you received constructive feedback. How did you respond?",
                ],
                "medium": [
                    "Describe a situation where you had to make a difficult technical decision with incomplete information. What was the outcome?",
                    "Tell me about a time you disagreed with your team lead on an approach. How did you handle it?",
                    "Give me an example of a time you had to balance speed with quality. What trade-offs did you make?",
                ],
                "hard": [
                    "Tell me about the most complex cross-team project you've led. How did you coordinate across teams and handle conflicting priorities?",
                    "Describe a situation where a project you owned was failing. What did you do to turn it around?",
                    "Tell me about a time you had to push back on a product requirement you believed was wrong. What happened?",
                ],
            },
            "technical": {
                "easy": [
                    f"Explain what {skills[0] if skills else 'REST APIs'} is and when you would use it.",
                    "What's the difference between a SQL and NoSQL database? When would you choose each?",
                    "Explain the concept of version control and why it's important in software development.",
                ],
                "medium": [
                    f"How would you design the architecture for a {role.lower()} project using {', '.join(skills[:3]) if skills else 'modern technologies'}?",
                    "Explain how you would handle error handling and logging in a production system.",
                    "Describe your approach to writing testable code. What patterns do you follow?",
                ],
                "hard": [
                    f"Design a scalable system that handles 10M daily active users for a {role.lower()} application. Walk me through your architecture decisions.",
                    "How would you debug a production issue where response times have increased 10x but CPU and memory look normal?",
                    "Explain the CAP theorem and how it applies to a distributed system you've worked on.",
                ],
            },
            "situational": {
                "easy": [
                    "If a stakeholder asked you to skip code review to meet a deadline, what would you do?",
                    "Your teammate's PR has been open for 3 days. How do you approach giving feedback?",
                ],
                "medium": [
                    "You discover a security vulnerability in production. The fix will take 2 days but you have a demo tomorrow. What do you do?",
                    "Your team is split 50/50 on a technical approach. Both have valid trade-offs. How do you move forward?",
                ],
                "hard": [
                    "You've been asked to rewrite a legacy system that 5 teams depend on. How do you plan and execute this?",
                    "A critical service your team owns goes down at 2 AM. Walk me through your incident response.",
                ],
            },
            "system_design": {
                "easy": [
                    "Design a URL shortener service. What components would you need?",
                    "Design a simple task management API. What endpoints and data models would you use?",
                ],
                "medium": [
                    "Design a real-time chat application. How would you handle message delivery, storage, and presence?",
                    "Design a job queue system that handles retries, dead letters, and priority ordering.",
                ],
                "hard": [
                    "Design a distributed rate limiter that works across multiple data centers.",
                    "Design a news feed system similar to Twitter/X that handles 100M users with real-time updates.",
                ],
            },
        }

        q_list = questions.get(q_type, questions["behavioral"]).get(difficulty, questions["behavioral"]["medium"])

        import random
        question = random.choice(q_list)

        tips = {
            "behavioral": "Use the STAR method: Situation, Task, Action, Result. Be specific with numbers and outcomes.",
            "technical": "Think out loud. Start with high-level approach, then dive into details. It's OK to say 'I'd need to research that.'",
            "situational": "Show your decision-making process. Explain trade-offs and how you'd communicate with stakeholders.",
            "system_design": "Start with requirements and constraints. Draw the high-level architecture first, then drill into components.",
        }

        return {
            "question": question,
            "type": q_type,
            "difficulty": difficulty,
            "tip": tips.get(q_type, "Be specific and use real examples from your experience."),
        }

    def _evaluate_answer(
        self, question: str, answer: str, role: str
    ) -> dict[str, Any]:
        """Evaluate a candidate's answer using STAR method criteria."""
        answer_lower = answer.lower()
        word_count = len(answer.split())

        # STAR evaluation
        star_scores = {}

        # Situation indicators
        situation_words = ["when", "while", "during", "at my", "at the", "in my role", "project", "team"]
        star_scores["situation"] = any(w in answer_lower for w in situation_words)

        # Task indicators
        task_words = ["needed to", "had to", "responsible for", "goal was", "challenge was", "tasked with", "objective"]
        star_scores["task"] = any(w in answer_lower for w in task_words)

        # Action indicators
        action_words = ["i built", "i created", "i designed", "i led", "i implemented", "i decided", "i proposed", "i wrote", "i developed", "i analyzed"]
        star_scores["action"] = any(w in answer_lower for w in action_words)

        # Result indicators
        result_words = ["resulted in", "led to", "improved", "reduced", "increased", "saved", "achieved", "delivered", "%", "percent"]
        star_scores["result"] = any(w in answer_lower for w in result_words)

        # Calculate score
        star_count = sum(1 for v in star_scores.values() if v)
        score = round(star_count / 4 * 100)

        # Generate feedback
        feedback = []
        strengths = []
        improvements = []

        if star_scores["situation"]:
            strengths.append("Good job setting the context with a specific situation")
        else:
            improvements.append("Start by describing the specific situation or context — where were you, what was happening?")

        if star_scores["task"]:
            strengths.append("Clearly articulated the task or challenge")
        else:
            improvements.append("Clarify what specifically you were responsible for or what the goal was")

        if star_scores["action"]:
            strengths.append("Described concrete actions you personally took")
        else:
            improvements.append("Focus on what YOU specifically did — use 'I' instead of 'we' and name concrete actions")

        if star_scores["result"]:
            strengths.append("Included results or outcomes")
        else:
            improvements.append("Always end with measurable results — numbers, percentages, or concrete outcomes")

        # Length feedback
        if word_count < 50:
            improvements.append(f"Your answer is quite short ({word_count} words). Aim for 100-200 words for a complete STAR response")
        elif word_count > 300:
            improvements.append(f"Your answer is quite long ({word_count} words). Try to be more concise — aim for 100-200 words")

        # Overall rating
        if score >= 75:
            rating = "Strong"
            feedback.append("This is a well-structured answer that covers the key STAR components.")
        elif score >= 50:
            rating = "Good"
            feedback.append("Solid foundation but could be strengthened with more specific details.")
        else:
            rating = "Needs Work"
            feedback.append("Focus on structuring your answer using the STAR method for a more compelling response.")

        return {
            "score": score,
            "rating": rating,
            "star_breakdown": star_scores,
            "strengths": strengths,
            "improvements": improvements,
            "feedback": feedback,
            "word_count": word_count,
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        mode = kwargs["mode"]
        role = kwargs["role_title"]

        if mode == "generate_question":
            q_type = kwargs.get("question_type", "behavioral")
            difficulty = kwargs.get("difficulty", "medium")
            skills = kwargs.get("required_skills", [])
            result = self._generate_question(role, q_type, difficulty, skills)
            return {"success": True, "mode": "generate_question", **result}

        elif mode == "evaluate_answer":
            question = kwargs.get("question", "")
            answer = kwargs.get("answer", "")
            if not question or not answer:
                return {"success": False, "error": "Both question and answer are required for evaluation"}
            result = self._evaluate_answer(question, answer, role)
            return {"success": True, "mode": "evaluate_answer", "question": question, **result}

        return {"success": False, "error": f"Unknown mode: {mode}"}
