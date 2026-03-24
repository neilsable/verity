"""
VERITY — Structured Logging Configuration
JSON logs compatible with Datadog / Grafana / Railway.
Every log line includes: timestamp, level, service, env, trace context.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings


def add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject app-level context into every log line."""
    settings = get_settings()
    event_dict["service"] = settings.dd_service
    event_dict["env"] = settings.app_env
    return event_dict


def setup_logging() -> None:
    """
    Configure structlog for structured JSON logging.
    In development: pretty-printed, coloured output.
    In production: JSON output for log aggregators.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]

    if settings.is_development:
        # Pretty output for local dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON for production log aggregators
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries emit structured logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy libraries in production
    if not settings.is_development:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named structlog logger. Use this in every module."""
    return structlog.get_logger(name)
