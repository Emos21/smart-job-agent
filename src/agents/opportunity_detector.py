"""Opportunity detector — agents detect opportunities and suggest goals autonomously.

6 trigger types with confidence thresholds and anti-spam controls:
- Max 2 suggestions per user per day
- 4-hour cooldown between suggestions for same user
- 7-day dedup: same cooldown_key won't re-trigger within 7 days
- auto_suggestions user preference toggle (default on)
- Minimum confidence threshold: 0.7
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .. import database as db


@dataclass
class Suggestion:
    """A goal suggestion from the opportunity detector."""
    title: str
    description: str
    trigger_type: str
    confidence: float
    cooldown_key: str
    agent_steps: list[dict] = field(default_factory=list)


class OpportunityDetector:
    """Detects opportunities and suggests goals based on user data."""

    MIN_CONFIDENCE = 0.7
    MAX_SUGGESTIONS_PER_DAY = 2
    COOLDOWN_HOURS = 4

    def detect(self, user_id: int) -> list[Suggestion]:
        """Scan user data and return suggestions above confidence threshold.

        Anti-spam controls are applied before returning.
        """
        # Check if user has auto_suggestions enabled
        if not db.get_auto_suggestions_enabled(user_id):
            return []

        # Check daily limit
        recent = db.get_recent_suggestions(user_id, hours=24)
        if len(recent) >= self.MAX_SUGGESTIONS_PER_DAY:
            return []

        # Check cooldown
        if recent:
            last_time = recent[0].get("created_at", "")
            if last_time:
                try:
                    last_dt = datetime.fromisoformat(last_time)
                    if datetime.now() - last_dt < timedelta(hours=self.COOLDOWN_HOURS):
                        return []
                except (ValueError, TypeError):
                    pass

        suggestions = []

        # Run each trigger check
        for check in [
            self._check_stale_saved_jobs,
            self._check_skill_gap,
            self._check_market_shift,
            self._check_profile_incomplete,
            self._check_application_followup,
            self._check_learning_opportunity,
        ]:
            try:
                result = check(user_id)
                if result and result.confidence >= self.MIN_CONFIDENCE:
                    # 7-day dedup check
                    existing = db.get_suggestion_by_cooldown_key(user_id, result.cooldown_key, days=7)
                    if not existing:
                        suggestions.append(result)
            except Exception:
                continue

            # Respect daily limit
            if len(suggestions) + len(recent) >= self.MAX_SUGGESTIONS_PER_DAY:
                break

        return suggestions

    def _check_stale_saved_jobs(self, user_id: int) -> Suggestion | None:
        """5+ saved jobs, 0 applications in 5 days."""
        jobs = db.get_jobs(user_id=user_id, limit=50)
        if len(jobs) < 5:
            return None

        apps = db.get_applications(user_id=user_id)
        recent_apps = [
            a for a in apps
            if a.get("updated_at", "") > (datetime.now() - timedelta(days=5)).isoformat()
        ]

        if len(recent_apps) == 0 and len(jobs) >= 5:
            return Suggestion(
                title="Start applying to your saved jobs",
                description=f"You have {len(jobs)} saved jobs but haven't applied to any recently. Let me help you pick the best ones and prepare your applications.",
                trigger_type="stale_saved_jobs",
                confidence=0.9,
                cooldown_key=f"stale_jobs_{user_id}",
                agent_steps=[
                    {"title": "Review saved jobs", "agent_name": "match"},
                    {"title": "Prepare application materials", "agent_name": "forge"},
                ],
            )
        return None

    def _check_skill_gap(self, user_id: int) -> Suggestion | None:
        """Match agent flagged missing skills 3+ times."""
        traces = db.get_traces(user_id, limit=30)
        match_traces = [t for t in traces if t.get("agent_name") == "match" and t.get("status") == "completed"]

        # Look for "missing" or "gap" in outputs
        gap_count = 0
        gap_skills = set()
        for trace in match_traces[:10]:
            output = (trace.get("output") or "").lower()
            if "missing" in output or "gap" in output or "lack" in output:
                gap_count += 1
                # Extract rough skill mentions
                for word in output.split():
                    if len(word) > 3 and word.isalpha():
                        gap_skills.add(word)

        if gap_count >= 3:
            return Suggestion(
                title="Address your skill gaps",
                description="Multiple job analyses have flagged skill gaps. A targeted learning plan could improve your match rates.",
                trigger_type="skill_gap_detected",
                confidence=0.85,
                cooldown_key=f"skill_gap_{user_id}",
                agent_steps=[
                    {"title": "Analyze skill gaps", "agent_name": "match"},
                    {"title": "Create learning path", "agent_name": "coach"},
                ],
            )
        return None

    def _check_market_shift(self, user_id: int) -> Suggestion | None:
        """Scout found 10+ new jobs in user's field."""
        profile = db.get_profile(user_id)
        if not profile or not profile.get("target_role"):
            return None

        # Check if there are many saved jobs recently
        jobs = db.get_jobs(user_id=user_id, limit=20)
        recent_jobs = [
            j for j in jobs
            if j.get("saved_at", "") > (datetime.now() - timedelta(days=7)).isoformat()
        ]

        if len(recent_jobs) >= 10:
            role = profile["target_role"]
            return Suggestion(
                title=f"Hot market for {role} roles",
                description=f"There are {len(recent_jobs)} new positions in your field this week. It's a great time to apply.",
                trigger_type="market_shift",
                confidence=0.75,
                cooldown_key=f"market_{user_id}_{role.lower().replace(' ', '_')}",
                agent_steps=[
                    {"title": "Search latest openings", "agent_name": "scout"},
                    {"title": "Rank best matches", "agent_name": "match"},
                ],
            )
        return None

    def _check_profile_incomplete(self, user_id: int) -> Suggestion | None:
        """Profile missing key sections."""
        profile = db.get_profile(user_id)
        if not profile:
            return Suggestion(
                title="Complete your profile",
                description="Set up your profile so I can give you personalized job recommendations and better matches.",
                trigger_type="profile_incomplete",
                confidence=0.95,
                cooldown_key=f"profile_incomplete_{user_id}",
                agent_steps=[],
            )

        missing = []
        if not profile.get("target_role"):
            missing.append("target role")
        if not profile.get("experience_level"):
            missing.append("experience level")
        if not profile.get("skills"):
            missing.append("skills")

        resumes = db.get_resumes(user_id)
        if not resumes:
            missing.append("resume")

        if len(missing) >= 2:
            return Suggestion(
                title="Complete your profile",
                description=f"Your profile is missing: {', '.join(missing)}. Completing it will improve AI recommendations.",
                trigger_type="profile_incomplete",
                confidence=0.95,
                cooldown_key=f"profile_missing_{user_id}_{'_'.join(missing)}",
                agent_steps=[],
            )
        return None

    def _check_application_followup(self, user_id: int) -> Suggestion | None:
        """Applied 7+ days ago, no status change."""
        apps = db.get_applications(user_id=user_id, status="applied")
        stale_apps = [
            a for a in apps
            if a.get("updated_at", "") < (datetime.now() - timedelta(days=7)).isoformat()
        ]

        if stale_apps:
            app = stale_apps[0]
            company = app.get("company", "a company")
            return Suggestion(
                title=f"Follow up with {company}",
                description=f"Your application to {company} has been pending for over a week. Let me help draft a follow-up email.",
                trigger_type="application_followup",
                confidence=0.8,
                cooldown_key=f"followup_{app.get('id')}",
                agent_steps=[
                    {"title": "Draft follow-up email", "agent_name": "forge"},
                ],
            )
        return None

    def _check_learning_opportunity(self, user_id: int) -> Suggestion | None:
        """Recurring skill gap + available resources."""
        # Simplified: check if user has been searching but not using learning tools
        traces = db.get_traces(user_id, limit=30)
        search_count = sum(1 for t in traces if t.get("agent_name") == "scout")
        learn_count = sum(1 for t in traces if "learn" in (t.get("task") or "").lower())

        if search_count >= 5 and learn_count == 0:
            return Suggestion(
                title="Boost your skills",
                description="You've been actively searching — a targeted learning plan could make you more competitive for the roles you're targeting.",
                trigger_type="learning_opportunity",
                confidence=0.7,
                cooldown_key=f"learning_{user_id}",
                agent_steps=[
                    {"title": "Identify key skills to learn", "agent_name": "match"},
                    {"title": "Create learning path", "agent_name": "coach"},
                ],
            )
        return None
