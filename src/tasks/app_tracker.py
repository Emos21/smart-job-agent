"""Application tracker task — checks for application status changes.

Periodic Celery task that runs every 12 hours.
Creates notifications for status updates.
"""

import json

from ..celery_app import celery_app
from .. import database as db
from .base_task import AutonomousTask


@celery_app.task(base=AutonomousTask, bind=True, name="src.tasks.app_tracker.track_all_applications")
def track_all_applications(self):
    """Check application status for all users."""
    conn = db.get_db()
    users = conn.execute(
        "SELECT DISTINCT user_id FROM applications WHERE user_id IS NOT NULL AND status = 'applied'"
    ).fetchall()
    conn.close()

    results = []
    for row in users:
        user_id = row["user_id"]
        try:
            result = _check_user_applications(user_id)
            results.append(result)
            self.checkpoint({"completed_users": [r["user_id"] for r in results]})
        except Exception as e:
            results.append({"user_id": user_id, "error": str(e)})

    return {"users_checked": len(results), "results": results}


def _check_user_applications(user_id: int) -> dict:
    """Check for stale applications and create reminders."""
    from datetime import datetime, timedelta

    apps = db.get_applications(user_id=user_id, status="applied")
    now = datetime.now()
    cutoff = (now - timedelta(days=7)).isoformat()

    stale_count = 0
    for app in apps:
        updated_at = app.get("updated_at", "")
        if updated_at < cutoff:
            app_id = app.get("id")
            title = app.get("title", "Unknown")
            company = app.get("company", "Unknown")

            # Deduplicate: check for existing unread notification
            conn = db.get_db()
            existing = conn.execute(
                "SELECT id FROM notifications WHERE user_id = ? AND type = 'application_followup' AND data LIKE ? AND read = 0",
                (user_id, f'%"application_id": {app_id}%'),
            ).fetchone()
            conn.close()

            if not existing:
                db.create_notification(
                    user_id=user_id,
                    type="application_followup",
                    title="Follow up on application",
                    message=f'Your application for "{title}" at {company} has been pending for over a week. Consider following up.',
                    data=json.dumps({"application_id": app_id}),
                )
                stale_count += 1

    return {"user_id": user_id, "stale_reminders": stale_count}
