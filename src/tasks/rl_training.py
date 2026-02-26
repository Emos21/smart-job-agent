"""Celery periodic task for RL model training.

Runs every 6 hours to update per-user RL models from recent traces.
"""

from ..celery_app import celery_app
from .. import database as db
from .base_task import AutonomousTask


@celery_app.task(base=AutonomousTask, bind=True, name="src.tasks.rl_training.train_all_active_users")
def train_all_active_users(self):
    """Train RL models for all users with recent traces."""
    from ..rl.trainer import RLTrainer

    trainer = RLTrainer()

    # Find users with recent traces (active in last 7 days)
    conn = db.get_db()
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM agent_traces "
        "WHERE started_at > datetime('now', '-7 days') AND user_id IS NOT NULL"
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        user_id = row["user_id"]
        try:
            result = trainer.train_batch(user_id)
            results.append(result)
            self.checkpoint({"completed_users": [r["user_id"] for r in results]})
        except Exception as e:
            results.append({"user_id": user_id, "error": str(e)})

    return {"users_trained": len(results), "results": results}
