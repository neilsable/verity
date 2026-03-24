"""
VERITY — Celery Tasks
Async task runners for research jobs.
Each task bridges the sync Celery world into the async LangGraph agent world.
"""

import asyncio
import uuid
from typing import Any

import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.worker import celery_app

logger = structlog.get_logger(__name__)


class ResearchTask(Task):
    """Base task class with shared async event loop management."""

    _loop: asyncio.AbstractEventLoop | None = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def run_async(self, coro: Any) -> Any:
        return self.loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="app.worker.tasks.run_research_job",
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    dont_autoretry_for=(SoftTimeLimitExceeded,),
)
def run_research_job(
    self: ResearchTask,
    job_id: str,
    ticker: str,
    research_brief: str,
) -> dict[str, Any]:
    """
    Main research job task. Dispatches to the LangGraph agent pipeline.
    Runs as a Celery task but executes async code via the event loop.
    """
    log = logger.bind(job_id=job_id, ticker=ticker, task_id=self.request.id)
    log.info("research_task_started")

    try:
        result = self.run_async(
            _execute_research_pipeline(job_id, ticker, research_brief)
        )
        log.info("research_task_completed", cost_usd=result.get("cost_usd"))
        return result

    except SoftTimeLimitExceeded:
        log.error("research_task_timeout", timeout_seconds=600)
        self.run_async(_mark_job_failed(job_id, "Research job timed out after 10 minutes"))
        raise

    except Exception as exc:
        log.exception("research_task_error", error=str(exc))
        self.run_async(_mark_job_failed(job_id, str(exc)))
        raise self.retry(exc=exc)


async def _execute_research_pipeline(
    job_id: str,
    ticker: str,
    research_brief: str,
) -> dict[str, Any]:
    """
    Async entry point for the LangGraph agent pipeline.
    TODO Phase 3: wire in the actual LangGraph graph.
    """
    # Placeholder — will be replaced in Phase 3
    from app.services.cache import publish_job_progress

    await publish_job_progress(job_id, {
        "event": "job_started",
        "job_id": job_id,
        "ticker": ticker,
    })

    return {"job_id": job_id, "status": "completed", "cost_usd": 0.0}


async def _mark_job_failed(job_id: str, error_message: str) -> None:
    """Update job status to failed in the database."""
    # TODO Phase 3: update DB
    logger.error("job_marked_failed", job_id=job_id, error=error_message)
