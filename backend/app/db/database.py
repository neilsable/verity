"""
VERITY — Async Database Connection Pool
SQLAlchemy 2.0 async engine for PostgreSQL via asyncpg.
"""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Global engine and session factory (initialised in lifespan)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Initialise the async database engine and connection pool."""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Check connection health before using
        pool_recycle=3600,   # Recycle connections after 1 hour
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    logger.info("database_connected", url=settings.database_url.split("@")[-1])


async def close_db() -> None:
    """Close the database connection pool gracefully."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("database_disconnected")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Commits on success, rolls back on exception.

    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
