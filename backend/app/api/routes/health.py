"""
VERITY — Health Check Endpoints
Used by Railway, load balancers, and monitoring tools.
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.database import get_db
from app.services.cache import get_redis

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """Basic liveness probe — just confirms the process is alive."""
    return {"status": "ok", "service": "verity-api"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> JSONResponse:
    """
    Readiness probe — checks all downstream dependencies.
    Returns 503 if any dependency is unavailable.
    """
    checks: dict[str, str] = {}
    healthy = True

    # Check PostgreSQL
    try:
        import asyncpg
        from app.core.config import get_settings
        settings = get_settings()
        conn = await asyncpg.connect(
            settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        await conn.execute("SELECT 1")
        await conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        healthy = False

    # Check Redis
    try:
        r = get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        healthy = False

    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )
