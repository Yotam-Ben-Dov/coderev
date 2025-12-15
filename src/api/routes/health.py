from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from src.core.config import settings

router = APIRouter()


class HealthStatus(BaseModel):
    status: Literal["healthy", "unhealthy"]
    version: str
    environment: str
    timestamp: datetime


class ReadinessStatus(BaseModel):
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
    TODO: Add actual dependency checks (DB, Redis, etc.)
    """
    checks = {
        "database": True,  # TODO: Implement actual check
        "redis": True,  # TODO: Implement actual check
    }

    all_ready = all(checks.values())

    return ReadinessStatus(
        status="ready" if all_ready else "not_ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )
