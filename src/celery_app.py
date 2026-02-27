"""Celery application configuration for long-running autonomous tasks.

Broker: Redis on localhost:6379/0
Result backend: Redis on localhost:6379/1
"""

import os

from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
REDIS_RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_RESULT_URL", "redis://localhost:6379/1"))

celery_app = Celery(
    "kaziai",
    broker=REDIS_URL,
    backend=REDIS_RESULT_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task execution
    task_soft_time_limit=3300,  # Soft limit at 55 minutes
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "rl-training-every-6h": {
        "task": "src.tasks.rl_training.train_all_active_users",
        "schedule": 6 * 60 * 60,  # 6 hours
    },
    "opportunity-scan-every-4h": {
        "task": "src.tasks.opportunity_scan.scan_all_users",
        "schedule": 4 * 60 * 60,  # 4 hours
    },
    "job-monitor-every-2h": {
        "task": "src.tasks.job_monitor.monitor_jobs_for_all_users",
        "schedule": 2 * 60 * 60,  # 2 hours
    },
    "application-tracker-every-12h": {
        "task": "src.tasks.app_tracker.track_all_applications",
        "schedule": 12 * 60 * 60,  # 12 hours
    },
}

# Auto-discover tasks in src.tasks
celery_app.autodiscover_tasks(["src.tasks"])
