"""Proactive suggestion engine for KaziAI.

Analyzes user state and generates context-aware suggestions.
Rule-based triggers — no LLM calls needed.
"""

from . import database as db


class SuggestionEngine:
    """Generates proactive suggestions based on user state."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    def generate(self) -> list[dict]:
        """Generate up to 3 prioritized suggestions."""
        suggestions = []

        profile = db.get_profile(self.user_id)
        resumes = db.get_resumes(self.user_id)
        jobs = db.get_jobs(self.user_id)
        applications = db.get_applications(self.user_id)
        goals = db.get_goals(self.user_id, status="active")

        # Priority 1: No profile set
        if not profile or not profile.get("target_role"):
            suggestions.append({
                "id": "complete_profile",
                "message": "Complete your profile for personalized advice",
                "action": "profile",
                "priority": 10,
            })

        # Priority 2: No resume uploaded
        if not resumes:
            suggestions.append({
                "id": "upload_resume",
                "message": "Upload your resume so I can tailor applications",
                "action": "chat:Upload my resume and analyze it",
                "priority": 9,
            })

        # Priority 3: Active goals with pending steps
        for goal in goals[:2]:
            steps = db.get_goal_steps(goal["id"])
            pending = [s for s in steps if s["status"] == "pending"]
            completed = [s for s in steps if s["status"] == "completed"]
            if pending:
                suggestions.append({
                    "id": f"goal_{goal['id']}",
                    "message": f"You have {len(pending)} steps left on '{goal['title']}'",
                    "action": "goals",
                    "priority": 8,
                })

        # Priority 4: Saved jobs with no applications
        saved_jobs_no_app = []
        applied_job_ids = {a.get("job_id") for a in applications}
        for job in jobs:
            if job["id"] not in applied_job_ids:
                saved_jobs_no_app.append(job)
        if saved_jobs_no_app:
            count = len(saved_jobs_no_app)
            suggestions.append({
                "id": "draft_cover_letters",
                "message": f"You have {count} saved job{'s' if count > 1 else ''} — want me to draft cover letters?",
                "action": "chat:Draft cover letters for my saved jobs",
                "priority": 7,
            })

        # Priority 5: Applications with no recent update (applied > 7 days ago)
        from datetime import datetime, timedelta
        stale_apps = []
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        for app in applications:
            if app.get("status") == "applied" and app.get("updated_at", "") < cutoff:
                stale_apps.append(app)
        if stale_apps:
            count = len(stale_apps)
            suggestions.append({
                "id": "follow_up",
                "message": f"{count} application{'s' if count > 1 else ''} sent over a week ago — draft follow-up emails?",
                "action": "chat:Draft follow-up emails for my applications",
                "priority": 6,
            })

        # Priority 6: No conversations yet (new user)
        conversations = db.get_conversations(self.user_id)
        if not conversations:
            suggestions.append({
                "id": "first_chat",
                "message": "Start a chat to search for jobs or get career advice",
                "action": "chat",
                "priority": 5,
            })

        # Sort by priority (highest first) and return top 3
        suggestions.sort(key=lambda s: s["priority"], reverse=True)
        return suggestions[:3]
