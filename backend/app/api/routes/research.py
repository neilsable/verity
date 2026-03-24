"""
VERITY — Research API Routes (Phase 4)
Fully wired to the LangGraph agent pipeline.

POST   /research/jobs              — create + queue a research job
GET    /research/jobs/{id}         — job status + agent progress
GET    /research/jobs/{id}/stream  — SSE real-time agent progress
GET    /research/reports/{id}      — full report with citations
GET    /research/history           — paginated job history
DELETE /research/jobs/{id}         — cancel a running job
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.routes.auth import get_current_user
from app.models.schemas import (
    AgentName,
    AgentProgress,
    JobStatus,
    PaginatedResponse,
    ResearchJobCreate,
    ResearchJobResponse,
    ResearchReport,
    SuccessResponse,
)
from app.services.cache import cache_delete, cache_get, cache_set, get_redis

logger = structlog.get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# In-memory job store (replaced by Supabase in Phase 6)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}


def _job_cache_key(job_id: str) -> str:
    return f"job:{job_id}:state"


async def _save_job(job: dict) -> None:
    _jobs[job["id"]] = job
    await cache_set(_job_cache_key(job["id"]), job, ttl_seconds=86400)


async def _load_job(job_id: str, user_id: str) -> dict:
    job = _jobs.get(job_id) or await cache_get(_job_cache_key(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    if job["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return job


# ---------------------------------------------------------------------------
# POST /research/jobs
# ---------------------------------------------------------------------------

@router.post(
    "/jobs",
    response_model=ResearchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new research job",
)
@limiter.limit("10/minute")
async def create_research_job(
    request: Request,
    body: ResearchJobCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResearchJobResponse:
    """
    Submit a new equity research job.
    Queues the full 8-agent pipeline via Celery.
    Subscribe to GET /jobs/{id}/stream for real-time progress.
    """
    job_id = str(uuid.uuid4())
    user_id = current_user["sub"]
    now = datetime.now(timezone.utc)

    agent_progress = [
        {"agent": a.value, "status": "pending", "started_at": None,
         "completed_at": None, "error": None, "metadata": {}}
        for a in AgentName
    ]

    job = {
        "id": job_id,
        "user_id": user_id,
        "ticker": body.ticker,
        "research_brief": body.research_brief,
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "completed_at": None,
        "agent_progress": agent_progress,
        "error_message": None,
        "cost_usd": None,
        "total_tokens": None,
        "celery_task_id": None,
    }

    await _save_job(job)

    # Dispatch to Celery
    try:
        from app.worker.tasks import run_research_job
        task = run_research_job.apply_async(
            args=[job_id, body.ticker, body.research_brief],
            queue="research",
        )
        job["celery_task_id"] = task.id
        job["status"] = "running"
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        await _save_job(job)

        logger.info("research_job_queued", job_id=job_id, ticker=body.ticker, task_id=task.id)

    except Exception as e:
        # Celery not running — run inline for dev/demo
        logger.warning("celery_unavailable_running_inline", error=str(e))
        asyncio.create_task(_run_inline(job_id, body.ticker, body.research_brief, user_id))

    return _job_to_response(job)


async def _run_inline(job_id: str, ticker: str, brief: str, user_id: str) -> None:
    """
    Run the research pipeline inline (no Celery).
    Used in development when the Celery worker isn't running.
    """
    try:
        from app.worker.tasks import _execute_research_pipeline
        result = await _execute_research_pipeline(job_id, ticker, brief)

        job = await cache_get(_job_cache_key(job_id)) or _jobs.get(job_id, {})
        job.update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cost_usd": result.get("cost_usd"),
        })
        await _save_job(job)

        # Cache the report
        if result.get("report"):
            await cache_set(f"report:{job_id}", result["report"], ttl_seconds=86400 * 7)

    except Exception as e:
        logger.exception("inline_pipeline_failed", job_id=job_id, error=str(e))
        job = await cache_get(_job_cache_key(job_id)) or _jobs.get(job_id, {})
        job.update({
            "status": "failed",
            "error_message": str(e),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await _save_job(job)


# ---------------------------------------------------------------------------
# GET /research/jobs/{job_id}
# ---------------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}",
    response_model=ResearchJobResponse,
    summary="Get job status and agent progress",
)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResearchJobResponse:
    """Get the current status and per-agent progress for a research job."""
    job = await _load_job(str(job_id), current_user["sub"])

    # Sync progress from Redis pub/sub events if available
    progress_key = f"job:{job_id}:progress_log"
    progress_log = await cache_get(progress_key) or []
    if progress_log:
        job = _apply_progress_events(job, progress_log)

    return _job_to_response(job)


# ---------------------------------------------------------------------------
# GET /research/jobs/{job_id}/stream  (SSE)
# ---------------------------------------------------------------------------

@router.get(
    "/jobs/{job_id}/stream",
    summary="Stream real-time agent progress via SSE",
)
async def stream_job_progress(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time agent progress.
    Each event is a JSON object with: event, agent, job_id, duration_ms.

    Connect from the frontend with:
        const es = new EventSource('/research/jobs/{id}/stream')
        es.onmessage = e => console.log(JSON.parse(e.data))
    """
    # Verify access
    await _load_job(str(job_id), current_user["sub"])

    async def event_stream():
        r = get_redis()
        pubsub = r.pubsub()
        channel = f"job:{job_id}:progress"
        await pubsub.subscribe(channel)

        # Send initial ping so the client knows the connection is live
        yield f"data: {json.dumps({'event': 'connected', 'job_id': str(job_id)})}\n\n"

        try:
            timeout = 0
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                    data = json.loads(message["data"])
                    # Close stream when job finishes
                    if data.get("event") in ("job_completed", "job_failed"):
                        break
                else:
                    # Keep-alive ping every 15s
                    await asyncio.sleep(1)
                    timeout += 1
                    if timeout % 15 == 0:
                        yield f"data: {json.dumps({'event': 'ping'})}\n\n"
                    if timeout > 600:  # 10 min max
                        break
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /research/reports/{job_id}
# ---------------------------------------------------------------------------

@router.get(
    "/reports/{job_id}",
    response_model=ResearchReport,
    summary="Get the completed research report with citations",
)
async def get_report(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResearchReport:
    """Retrieve the completed research report including all citations and critique flags."""
    job = await _load_job(str(job_id), current_user["sub"])

    if job["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job['status']} — report not ready yet",
        )

    report_data = await cache_get(f"report:{job_id}")
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report data not found. It may have expired.",
        )

    return ResearchReport(**report_data)


# ---------------------------------------------------------------------------
# GET /research/history
# ---------------------------------------------------------------------------

@router.get(
    "/history",
    response_model=PaginatedResponse,
    summary="Get paginated job history for the current user",
)
async def get_research_history(
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """List all research jobs for the authenticated user, newest first."""
    user_id = current_user["sub"]

    # Filter jobs for this user
    user_jobs = [j for j in _jobs.values() if j.get("user_id") == user_id]
    user_jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

    total = len(user_jobs)
    start = (page - 1) * page_size
    page_jobs = user_jobs[start : start + page_size]

    return PaginatedResponse(
        items=[_job_to_response(j).model_dump() for j in page_jobs],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(start + page_size) < total,
    )


# ---------------------------------------------------------------------------
# DELETE /research/jobs/{job_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/jobs/{job_id}",
    response_model=SuccessResponse,
    summary="Cancel a pending or running job",
)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SuccessResponse:
    """Cancel a research job. Revokes the Celery task if running."""
    job = await _load_job(str(job_id), current_user["sub"])

    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a job with status: {job['status']}",
        )

    # Revoke Celery task
    if job.get("celery_task_id"):
        try:
            from app.worker import celery_app
            celery_app.control.revoke(job["celery_task_id"], terminate=True)
        except Exception as e:
            logger.warning("celery_revoke_failed", error=str(e))

    job["status"] = "cancelled"
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _save_job(job)

    logger.info("job_cancelled", job_id=str(job_id))
    return SuccessResponse(message=f"Job {job_id} cancelled.")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _job_to_response(job: dict) -> ResearchJobResponse:
    """Convert raw job dict to the API response model."""
    def _parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    progress = []
    for p in job.get("agent_progress", []):
        progress.append(AgentProgress(
            agent=p["agent"],
            status=p["status"],
            started_at=_parse_dt(p.get("started_at")),
            completed_at=_parse_dt(p.get("completed_at")),
            error=p.get("error"),
            metadata=p.get("metadata", {}),
        ))

    return ResearchJobResponse(
        id=uuid.UUID(job["id"]),
        ticker=job["ticker"],
        research_brief=job["research_brief"],
        status=job["status"],
        created_at=_parse_dt(job["created_at"]) or datetime.now(timezone.utc),
        updated_at=_parse_dt(job["updated_at"]) or datetime.now(timezone.utc),
        completed_at=_parse_dt(job.get("completed_at")),
        agent_progress=progress,
        error_message=job.get("error_message"),
        cost_usd=job.get("cost_usd"),
        total_tokens=job.get("total_tokens"),
    )


def _apply_progress_events(job: dict, events: list[dict]) -> dict:
    """Apply a list of progress events to a job's agent_progress list."""
    agent_map = {p["agent"]: p for p in job.get("agent_progress", [])}

    for event in events:
        agent = event.get("agent")
        if not agent or agent not in agent_map:
            continue

        evt = event.get("event", "")
        if evt == "agent_started":
            agent_map[agent]["status"] = "running"
            agent_map[agent]["started_at"] = event.get("timestamp")
        elif evt == "agent_completed":
            agent_map[agent]["status"] = "completed"
            agent_map[agent]["completed_at"] = event.get("timestamp")
        elif evt == "agent_failed":
            agent_map[agent]["status"] = "failed"
            agent_map[agent]["error"] = event.get("error")

    job["agent_progress"] = list(agent_map.values())
    return job
