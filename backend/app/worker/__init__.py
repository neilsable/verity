"""
VERITY — Celery Worker Application
Async task processing for research jobs.
"""

from celery import Celery
from celery.signals import worker_init, worker_shutdown

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()

celery_app = Celery(
    "verity",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,               # Only ack after task completes (safer)
    worker_prefetch_multiplier=1,      # One task at a time per worker slot
    task_soft_time_limit=settings.research_job_timeout_seconds,
    task_time_limit=settings.research_job_timeout_seconds + 60,
    task_routes={
        "app.worker.tasks.run_research_job": {"queue": "research"},
        "app.worker.tasks.*": {"queue": "default"},
    },
    beat_schedule={},
)


@worker_init.connect
def on_worker_init(**kwargs) -> None:
    setup_logging()


@worker_shutdown.connect
def on_worker_shutdown(**kwargs) -> None:
    import structlog
    structlog.get_logger(__name__).info("celery_worker_shutdown")
