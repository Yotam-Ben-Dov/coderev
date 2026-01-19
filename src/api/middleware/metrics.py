"""
Prometheus metrics middleware for FastAPI.

Automatically tracks:
- Request count by method, endpoint, and status code
- Request duration histograms
- Requests in progress gauge
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp

from src.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that collects Prometheus metrics for all HTTP requests.

    Metrics collected:
    - coderev_http_requests_total: Counter of total requests
    - coderev_http_request_duration_seconds: Histogram of request durations
    - coderev_http_requests_in_progress: Gauge of concurrent requests
    """

    # Endpoints to exclude from metrics (health checks, metrics endpoint itself)
    EXCLUDE_PATHS: set[str] = {"/health", "/ready", "/metrics"}

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and record metrics."""
        path = request.url.path

        # Skip metrics for excluded paths
        if path in self.EXCLUDE_PATHS:
            response = await call_next(request)
            return response

        # Get the matched route pattern (e.g., /reviews/{review_id} instead of /reviews/123)
        endpoint = self._get_path_template(request)
        method = request.method

        # Track in-progress requests
        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=method,
            endpoint=endpoint,
        ).inc()

        start_time = time.perf_counter()
        status_code = 500  # Default in case of unhandled exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            # Record duration
            duration = time.perf_counter() - start_time

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            # Record request count
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()

            # Decrement in-progress gauge
            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=method,
                endpoint=endpoint,
            ).dec()

    def _get_path_template(self, request: Request) -> str:
        """
        Get the path template instead of the actual path.

        This converts /reviews/123 to /reviews/{review_id} for better
        metric aggregation.
        """
        # Try to match against app routes
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                # route.path is the template like /reviews/{review_id}
                return str(getattr(route, "path", request.url.path))

        # Fallback to the actual path if no route matched
        return request.url.path
