"""
VERITY — FastAPI Application Entry Point
Production-grade setup with: auth middleware, rate limiting, structured logging,
CORS, request tracing, health checks, and graceful shutdown.
"""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.routes import health, research, auth

logger = structlog.get_logger(__name__)
settings = get_settings()

# Rate limiter — keyed on client IP
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup and shutdown logic.
    Initialise connections on startup, close them on shutdown.
    """
    setup_logging()
    print(f"VERITY starting env={settings.app_env}")

    # Startup: initialise DB pool, Redis, Pinecone
    from app.db.database import init_db
    from app.services.cache import init_redis

    await init_db()
    await init_redis()

    logger.info("verity_ready", host=settings.api_host, port=settings.api_port)

    yield  # Application runs here

    # Shutdown: close all connections gracefully
    from app.db.database import close_db
    from app.services.cache import close_redis

    await close_db()
    await close_redis()
    logger.info("verity_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="VERITY Equity Research API",
        description="Autonomous multi-agent equity research platform",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ------------------------------------------------------------------
    # Request Tracing Middleware
    # Adds X-Request-ID header and logs every request with timing.
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def request_tracing_middleware(
        request: Request, call_next: any
    ) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request context to all logs within this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("request_unhandled_error", error=str(exc))
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response

    # ------------------------------------------------------------------
    # Global Exception Handler
    # ------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    app.include_router(
        research.router,
        prefix="/research",
        tags=["Research"],
    )

    return app


app = create_app()
