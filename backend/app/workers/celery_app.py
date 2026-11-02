from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "controller_tuner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.ga_tasks", "app.workers.maintenance"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=3,
    result_expires=settings.job_retention_seconds,
    task_soft_time_limit=int(settings.ga_task_soft_time_limit),
    task_time_limit=int(settings.ga_task_time_limit),
    task_routes={
        "app.workers.ga_tasks.run_optimization": {"queue": "ga"},
        "app.workers.maintenance.*": {"queue": "maintenance"},
    },
    beat_schedule={
        "cleanup-terminal-jobs": {
            "task": "app.workers.maintenance.cleanup_terminal_jobs",
            "schedule": 300.0,
        },
        "cleanup-expired-runs": {
            "task": "app.workers.maintenance.cleanup_expired_runs",
            "schedule": 300.0,
        },
        "cleanup-orphan-artifacts": {
            "task": "app.workers.maintenance.cleanup_orphan_artifacts",
            "schedule": 900.0,
        },
        "delete-expired-systems": {
            "task": "app.workers.maintenance.delete_expired_systems",
            "schedule": crontab(minute="*/10"),
        },
    },
)
