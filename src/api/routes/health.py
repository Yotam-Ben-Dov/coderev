"""Health check endpoints."""

from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from src.core.config import settings
from src.db.session import check_db_connection

router = APIRouter()
logger = structlog.get_logger()


class HealthStatus(BaseModel):
    """Basic health check response."""

    status: Literal["healthy", "unhealthy"]
    version: str
    environment: str
    timestamp: datetime


class ReadinessStatus(BaseModel):
    """Readiness check response with dependency status."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]
    timestamp: datetime


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint.

    Used by load balancers and container orchestrators to verify
    the application is running.
    """
    return HealthStatus(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessStatus)
async def readiness_check() -> ReadinessStatus:
    """
    Readiness check endpoint.

    Verifies all dependencies are available before accepting traffic.
    """
    # Check database connection
    db_healthy = await check_db_connection()

    # TODO: Add Redis check when Celery is implemented
    redis_healthy = True  # Placeholder

    checks = {
        "database": db_healthy,
        "redis": redis_healthy,
    }

    all_ready = all(checks.values())

    if not all_ready:
        logger.warning("Readiness check failed", checks=checks)

    return ReadinessStatus(
        status="ready" if all_ready else "not_ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )
