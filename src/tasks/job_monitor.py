"""Job monitor task — scans job boards for new postings matching user criteria.

Periodic Celery task that runs the Scout agent per user with saved search queries.
Checkpoints after each user to survive crashes.
"""

import json

from ..celery_app import celery_app
from .. import database as db
from .base_task import AutonomousTask


@celery_app.task(base=AutonomousTask, bind=True, name="src.tasks.job_monitor.monitor_jobs_for_all_users")
def monitor_jobs_for_all_users(self):
    """Scan for new jobs for all users with profiles and saved jobs."""
    conn = db.get_db()
    users = conn.execute(
        "SELECT DISTINCT u.id FROM users u "
        "JOIN user_profiles up ON up.user_id = u.id "
        "WHERE up.target_role != ''"
    ).fetchall()
    conn.close()

    results = []
    for row in users:
        user_id = row["id"]
        try:
            result = _scan_for_user(user_id)
            results.append(result)
            self.checkpoint({"completed_users": [r["user_id"] for r in results]})
        except Exception as e:
            results.append({"user_id": user_id, "error": str(e)})

    return {"users_scanned": len(results), "results": results}


def _scan_for_user(user_id: int) -> dict:
    """Search for new jobs matching a user's profile."""
    profile = db.get_profile(user_id)
    if not profile:
        return {"user_id": user_id, "skipped": True, "reason": "no profile"}

    target_role = profile.get("target_role", "")
    skills = profile.get("skills", [])
    if not target_role and not skills:
        return {"user_id": user_id, "skipped": True, "reason": "no search criteria"}

    # Build search keywords from profile
    keywords = []
    if target_role:
        keywords.append(target_role)
    keywords.extend(skills[:5])

    # Run search via tool
    try:
        from ..tools.job_search import JobSearchTool
        tool = JobSearchTool()
        result = tool.execute(keywords=keywords, max_results=10)
        jobs = result.get("jobs", [])
    except Exception:
        jobs = []

    if not jobs:
        return {"user_id": user_id, "new_jobs": 0}

    # Check which jobs are new (not already saved)
    existing_urls = set()
    saved = db.get_jobs(user_id=user_id, limit=100)
    for j in saved:
        if j.get("url"):
            existing_urls.add(j["url"])

    new_jobs = [j for j in jobs if j.get("url") and j["url"] not in existing_urls]

    if new_jobs:
        db.create_notification(
            user_id=user_id,
            type="new_jobs_found",
            title=f"{len(new_jobs)} new job{'s' if len(new_jobs) != 1 else ''} found",
            message=f"Found {len(new_jobs)} new {target_role} positions matching your profile.",
            data=json.dumps({"count": len(new_jobs), "preview": [j.get("title", "") for j in new_jobs[:3]]}),
        )

    return {"user_id": user_id, "new_jobs": len(new_jobs)}
