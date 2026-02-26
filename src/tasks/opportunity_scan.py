"""Celery periodic task for opportunity detection.

Runs every 4 hours to scan all users and create goal suggestions.
"""

import json

from ..celery_app import celery_app
from .. import database as db
from .base_task import AutonomousTask


@celery_app.task(base=AutonomousTask, bind=True, name="src.tasks.opportunity_scan.scan_all_users")
def scan_all_users(self):
    """Run opportunity detection for all users with auto_suggestions enabled."""
    from ..agents.opportunity_detector import OpportunityDetector

    detector = OpportunityDetector()

    # Find all users with profiles
    conn = db.get_db()
    users = conn.execute(
        "SELECT DISTINCT u.id FROM users u "
        "JOIN user_profiles up ON up.user_id = u.id "
        "WHERE up.auto_suggestions = 1"
    ).fetchall()
    conn.close()

    total_suggestions = 0
    for row in users:
        user_id = row["id"]
        try:
            suggestions = detector.detect(user_id)
            for suggestion in suggestions:
                # Create goal with agent_suggested origin
                goal_id = db.create_goal_with_origin(
                    user_id=user_id,
                    title=suggestion.title,
                    description=suggestion.description,
                    origin="agent_suggested",
                    trigger_type=suggestion.trigger_type,
                )

                # Add goal steps if specified
                for i, step in enumerate(suggestion.agent_steps, 1):
                    db.add_goal_step(
                        goal_id=goal_id,
                        step_number=i,
                        title=step.get("title", ""),
                        agent_name=step.get("agent_name", ""),
                    )

                # Log for anti-spam
                db.log_goal_suggestion(
                    user_id=user_id,
                    trigger_type=suggestion.trigger_type,
                    cooldown_key=suggestion.cooldown_key,
                    confidence=suggestion.confidence,
                    goal_id=goal_id,
                )

                # Create notification
                db.create_notification(
                    user_id=user_id,
                    type="goal_suggested",
                    title=f"Suggestion: {suggestion.title}",
                    message=suggestion.description,
                    data=json.dumps({
                        "goal_id": goal_id,
                        "trigger_type": suggestion.trigger_type,
                        "confidence": suggestion.confidence,
                    }),
                )

                # Push via WebSocket
                try:
                    import asyncio
                    from ..websocket_manager import ws_manager
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(ws_manager.send_to_user(user_id, {
                            "type": "notification",
                            "notification_type": "goal_suggested",
                            "title": f"Suggestion: {suggestion.title}",
                        }))
                except Exception:
                    pass

                total_suggestions += 1

            self.checkpoint({"users_scanned": user_id, "total_suggestions": total_suggestions})
        except Exception:
            continue

    return {"users_scanned": len(users), "suggestions_created": total_suggestions}
