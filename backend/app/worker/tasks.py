"""
VERITY — Celery Tasks (Phase 3 update)
Wires the LangGraph agent pipeline into the async task runner.
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
    log = logger.bind(job_id=job_id, ticker=ticker, task_id=self.request.id)
    log.info("research_task_started")
    try:
        result = self.run_async(
            _execute_research_pipeline(job_id, ticker, research_brief)
        )
        log.info("research_task_completed", cost_usd=result.get("cost_usd"))
        return result
    except SoftTimeLimitExceeded:
        log.error("research_task_timeout")
        self.run_async(_mark_job_failed(job_id, "Research job timed out"))
        raise
    except Exception as exc:
        log.exception("research_task_error", error=str(exc))
        self.run_async(_mark_job_failed(job_id, str(exc)))
        raise self.retry(exc=exc)


async def _execute_research_pipeline(
    job_id: str, ticker: str, research_brief: str,
) -> dict[str, Any]:
    from app.agents.graph import research_graph
    from app.models.schemas import ResearchState
    from app.services.cache import publish_job_progress

    await publish_job_progress(job_id, {"event": "job_started", "job_id": job_id, "ticker": ticker})

    initial_state = ResearchState(
        job_id=uuid.UUID(job_id),
        ticker=ticker.upper(),
        research_brief=research_brief,
    )

    final_state = await research_graph.ainvoke(initial_state)
    report = final_state.final_report
    cost = final_state.total_cost_usd

    await publish_job_progress(job_id, {
        "event": "job_completed", "job_id": job_id, "cost_usd": cost,
        "citations": len(report.citations) if report else 0,
        "confidence": report.overall_confidence if report else 0,
    })

    return {
        "job_id": job_id, "status": "completed", "cost_usd": cost,
        "errors": final_state.errors,
        "report_id": str(report.report_id) if report else None,
    }


async def _mark_job_failed(job_id: str, error_message: str) -> None:
    logger.error("job_marked_failed", job_id=job_id, error=error_message)
    try:
        from app.services.cache import publish_job_progress
        await publish_job_progress(job_id, {"event": "job_failed", "job_id": job_id, "error": error_message})
    except Exception:
        pass
