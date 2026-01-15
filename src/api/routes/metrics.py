"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Returns Prometheus-formatted metrics for scraping.",
    response_class=Response,
)
async def metrics() -> Response:
    """
    Expose Prometheus metrics.
    
    This endpoint returns all registered metrics in the Prometheus
    text exposition format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )