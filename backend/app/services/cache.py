"""
VERITY — Redis Cache Service
Async Redis client for caching, job state, and pub/sub.
"""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Initialise the async Redis connection pool."""
    global _redis
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connection
    await _redis.ping()
    logger.info("redis_connected", url=settings.redis_url)


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("redis_disconnected")


def get_redis() -> aioredis.Redis:
    """Get the Redis client. Must call init_redis() first."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis


async def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> None:
    """Set a JSON-serialisable value in the cache."""
    r = get_redis()
    await r.set(key, json.dumps(value), ex=ttl_seconds)


async def cache_get(key: str) -> Any | None:
    """Get a value from the cache. Returns None if not found."""
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_delete(key: str) -> None:
    """Delete a key from the cache."""
    r = get_redis()
    await r.delete(key)


async def publish_job_progress(job_id: str, event: dict[str, Any]) -> None:
    """Publish a job progress event to the pub/sub channel."""
    r = get_redis()
    channel = f"job:{job_id}:progress"
    await r.publish(channel, json.dumps(event))
