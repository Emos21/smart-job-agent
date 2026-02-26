"""Background monitor for proactive notifications.

Periodically checks for:
- Stalled goals (active goals with no progress in 24h)
- Stale applications (status "applied" with no update in 7 days)

Creates notifications so the system acts without user input.
"""

import os
from datetime import datetime, timedelta

from . import database as db

_scheduler = None


def check_stalled_goals() -> None:
    """Find active goals with stalled progress and create notifications."""
    conn = db.get_db()
    now = datetime.now()
    cutoff = (now - timedelta(hours=24)).isoformat()

    # Find active goals where the last completed step is older than 24h
    # and there are still pending steps
    rows = conn.execute("""
        SELECT g.id, g.user_id, g.title,
               MAX(gs.completed_at) as last_activity
        FROM goals g
        JOIN goal_steps gs ON gs.goal_id = g.id
        WHERE g.status = 'active'
        GROUP BY g.id
        HAVING last_activity < ? OR last_activity IS NULL
    """, (cutoff,)).fetchall()

    for row in rows:
        goal_id = row["id"]
        user_id = row["user_id"]
        title = row["title"]

        # Check if there are pending steps
        pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM goal_steps WHERE goal_id = ? AND status = 'pending'",
            (goal_id,),
        ).fetchone()

        if not pending or pending["cnt"] == 0:
            continue

        # Deduplicate: don't create if we already have an unread notification for this goal
        existing = conn.execute(
            "SELECT id FROM notifications WHERE user_id = ? AND type = 'goal_stalled' AND data LIKE ? AND read = 0",
            (user_id, f'%"goal_id": {goal_id}%'),
        ).fetchone()

        if existing:
            continue

        import json
        db.create_notification(
            user_id=user_id,
            type="goal_stalled",
            title="Goal needs attention",
            message=f'Your goal "{title}" has pending steps with no progress in 24+ hours.',
            data=json.dumps({"goal_id": goal_id}),
        )

    conn.close()


def check_stale_applications() -> None:
    """Find applications stuck in 'applied' status for 7+ days."""
    conn = db.get_db()
    now = datetime.now()
    cutoff = (now - timedelta(days=7)).isoformat()

    rows = conn.execute("""
        SELECT a.id, a.user_id, a.updated_at, j.title, j.company
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.status = 'applied' AND a.updated_at < ?
    """, (cutoff,)).fetchall()

    for row in rows:
        app_id = row["id"]
        user_id = row["user_id"]
        title = row["title"]
        company = row["company"]

        # Deduplicate
        existing = conn.execute(
            "SELECT id FROM notifications WHERE user_id = ? AND type = 'application_reminder' AND data LIKE ? AND read = 0",
            (user_id, f'%"application_id": {app_id}%'),
        ).fetchone()

        if existing:
            continue

        import json
        db.create_notification(
            user_id=user_id,
            type="application_reminder",
            title="Follow up on application",
            message=f'Your application for "{title}" at {company} has been in "applied" status for over a week.',
            data=json.dumps({"application_id": app_id}),
        )

    conn.close()


def start_scheduler() -> None:
    """Start the background scheduler for periodic checks."""
    global _scheduler

    # Don't start in test mode
    if os.getenv("TESTING") == "1":
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        print("[background] apscheduler not installed, skipping background monitor")
        return

    if _scheduler is not None:
        return  # already running

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(check_stalled_goals, "interval", hours=4, id="check_stalled_goals")
    _scheduler.add_job(check_stale_applications, "interval", hours=12, id="check_stale_applications")
    _scheduler.start()
    print("[background] Scheduler started — goals every 4h, apps every 12h")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[background] Scheduler stopped")
