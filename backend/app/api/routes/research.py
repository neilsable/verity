"""
VERITY — Research API Routes
POST  /research/jobs         — create a new research job
GET   /research/jobs/{id}    — job status + SSE stream
GET   /research/reports/{id} — full report with citations
GET   /research/history      — user's job history
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.routes.auth import get_current_user
from app.models.schemas import (
    PaginatedResponse,
    ResearchJobCreate,
    ResearchJobResponse,
    ResearchReport,
    SuccessResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


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
    The job is queued and agents run asynchronously.
    Poll GET /jobs/{id} or subscribe to SSE stream for progress.
    """
    from datetime import datetime, timezone
    from app.services.cache import publish_job_progress

    job_id = uuid.uuid4()
    user_id = current_user["sub"]

    logger.info(
        "research_job_created",
        job_id=str(job_id),
        ticker=body.ticker,
        user_id=user_id,
    )

    # TODO Phase 3: dispatch to Celery worker
    # from app.worker.tasks import run_research_job
    # run_research_job.apply_async(
    #     args=[str(job_id), body.ticker, body.research_brief],
    #     queue="research",
    # )

    return ResearchJobResponse(
        id=job_id,
        ticker=body.ticker,
        research_brief=body.research_brief,
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ResearchJobResponse,
    summary="Get job status",
)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResearchJobResponse:
    """Get the current status and agent progress for a research job."""
    # TODO Phase 3: fetch from DB
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job {job_id} not found",
    )


@router.get(
    "/jobs/{job_id}/stream",
    summary="Stream job progress via SSE",
)
async def stream_job_progress(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time agent progress.
    Frontend subscribes to this to show which agent is currently running.
    """
    import asyncio
    import json

    from app.services.cache import get_redis

    async def event_generator():
        r = get_redis()
        pubsub = r.pubsub()
        channel = f"job:{job_id}:progress"
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get(
    "/reports/{job_id}",
    response_model=ResearchReport,
    summary="Get full research report",
)
async def get_report(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResearchReport:
    """Retrieve the completed research report with citations."""
    # TODO Phase 3: fetch from DB
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report for job {job_id} not found",
    )


@router.get(
    "/history",
    response_model=PaginatedResponse,
    summary="Get user's research history",
)
async def get_research_history(
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """List all research jobs for the authenticated user."""
    # TODO Phase 3: fetch from DB with pagination
    return PaginatedResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        has_more=False,
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=SuccessResponse,
    summary="Cancel a running job",
)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SuccessResponse:
    """Cancel a pending or running research job."""
    # TODO Phase 3: revoke Celery task and update DB
    return SuccessResponse(message=f"Job {job_id} cancellation requested.")
