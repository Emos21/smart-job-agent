"""Base class for autonomous tasks with checkpointing and crash recovery."""

import json
from datetime import datetime

from celery import Task

from .. import database as db


class AutonomousTask(Task):
    """Base Celery task with checkpoint/restore and failure handling.

    Subclasses implement run() and can call self.checkpoint() to save
    intermediate progress. On crash/restart, self.restore() loads the
    last checkpoint.

    Limits:
    - Max runtime: 1 hour per execution (enforced by Celery time_limit)
    - Max total runs: 24 per task instance per day
    """

    abstract = True
    max_retries = 3
    _task_db_id: int | None = None

    def checkpoint(self, state_dict: dict) -> None:
        """Save intermediate progress to the database."""
        if self._task_db_id:
            try:
                db.update_autonomous_task(
                    self._task_db_id,
                    state=json.dumps(state_dict),
                    status="running",
                )
            except Exception:
                pass

    def restore(self, task_db_id: int) -> dict | None:
        """Load last checkpoint state. Returns None if no checkpoint."""
        try:
            task = db.get_autonomous_task(task_db_id)
            if task and task.get("state"):
                return json.loads(task["state"])
        except Exception:
            pass
        return None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure — create notification and update status."""
        db_id = kwargs.get("task_db_id") or (args[0] if args else None)
        user_id = kwargs.get("user_id")

        if db_id:
            try:
                db.update_autonomous_task(db_id, status="failed")
            except Exception:
                pass

        if user_id:
            try:
                db.create_notification(
                    user_id=user_id,
                    type="task_failed",
                    title="Background task failed",
                    message=f"Task failed: {str(exc)[:200]}",
                    data=json.dumps({"task_db_id": db_id, "error": str(exc)[:500]}),
                )
            except Exception:
                pass

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task completion — update status."""
        db_id = kwargs.get("task_db_id") or (args[0] if args else None)
        if db_id:
            try:
                db.update_autonomous_task(
                    db_id,
                    status="completed",
                    result_summary=json.dumps(retval) if retval else None,
                )
            except Exception:
                pass

    def init_task(self, user_id: int, task_type: str, config: dict | None = None) -> int:
        """Create a task record in the database and return its ID."""
        task_db_id = db.create_autonomous_task(
            user_id=user_id,
            task_type=task_type,
            celery_task_id=self.request.id if self.request else "",
            config=json.dumps(config or {}),
        )
        self._task_db_id = task_db_id
        return task_db_id
