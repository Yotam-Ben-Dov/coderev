"""Database session management for CodeRev."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings
from src.db.models import Base

logger = structlog.get_logger()

# =============================================================================
# Engine Configuration
# =============================================================================


def create_engine() -> AsyncEngine:
    """Create the async database engine."""
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,  # Log SQL in debug mode
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour
    )


# Global engine instance (created lazily)
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


# =============================================================================
# Session Factory
# =============================================================================


def create_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Create a session factory."""
    if engine is None:
        engine = get_engine()
    
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Don't expire objects after commit
        autoflush=False,  # Manual flush control
    )


# Global session factory
async_session_factory = create_session_factory


# =============================================================================
# Session Dependencies
# =============================================================================


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Usage in FastAPI:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    factory = create_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting a database session.
    
    Usage:
        async with get_session_context() as session:
            # do stuff
    """
    factory = create_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# Database Initialization
# =============================================================================


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    Note: In production, use Alembic migrations instead.
    This is mainly for development/testing.
    """
    engine = get_engine()
    
    logger.info("Initializing database", url=settings.database_url.split("@")[-1])
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")


async def drop_db() -> None:
    """
    Drop all database tables.
    
    WARNING: This will delete all data. Only use in testing.
    """
    engine = get_engine()
    
    logger.warning("Dropping all database tables")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped")


async def close_db() -> None:
    """Close database connections."""
    global _engine
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database connections closed")


# =============================================================================
# Health Check
# =============================================================================


async def check_db_connection() -> bool:
    """
    Check if the database connection is healthy.
    
    Returns:
        True if connection is healthy, False otherwise.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False