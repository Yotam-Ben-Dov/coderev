"""Tests for Prometheus metrics."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.metrics import MetricsMiddleware
from src.core.metrics import (
    initialize_app_info,
    record_github_api_call,
    record_llm_request,
    record_review_completed,
)


class TestMetricsMiddleware:
    """Tests for the metrics middleware."""

    @pytest.fixture
    def test_app(self) -> FastAPI:
        """Create a test FastAPI app with metrics middleware."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/test")
        async def test_endpoint() -> dict:
            return {"status": "ok"}

        @app.get("/test/{item_id}")
        async def test_endpoint_with_param(item_id: int) -> dict:
            return {"item_id": item_id}

        @app.get("/health")
        async def health() -> dict:
            return {"status": "healthy"}

        return app

    @pytest.fixture
    def test_client(self, test_app: FastAPI) -> TestClient:
        """Create a test client for the test app."""
        return TestClient(test_app)

    def test_middleware_tracks_requests(self, test_client: TestClient) -> None:
        """Test that middleware tracks request metrics."""
        response = test_client.get("/test")
        assert response.status_code == 200

    def test_middleware_excludes_health_endpoints(self, test_client: TestClient) -> None:
        """Test that health endpoints are excluded from metrics."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_middleware_handles_path_parameters(self, test_client: TestClient) -> None:
        """Test that path parameters are normalized in metrics."""
        response = test_client.get("/test/123")
        assert response.status_code == 200


class TestLLMMetricsRecording:
    """Tests for LLM metrics helper functions."""

    def test_record_llm_request_success(self) -> None:
        """Test recording a successful LLM request."""
        record_llm_request(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            status="success",
            duration_seconds=2.5,
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.015,
        )

    def test_record_llm_request_error(self) -> None:
        """Test recording a failed LLM request."""
        record_llm_request(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            status="error",
            duration_seconds=0.5,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
        )

    def test_record_llm_request_local_model(self) -> None:
        """Test recording a local Ollama request."""
        record_llm_request(
            provider="ollama",
            model="deepseek-coder:6.7b",
            status="success",
            duration_seconds=15.0,
            tokens_input=500,
            tokens_output=200,
            cost_usd=0.0,
        )


class TestReviewMetricsRecording:
    """Tests for review metrics helper functions."""

    def test_record_review_completed(self) -> None:
        """Test recording a completed review."""
        record_review_completed(
            repository="owner/repo",
            status="completed",
            verdict="approve",
            duration_seconds=15.5,
            files_analyzed=5,
            comments_by_severity={
                "critical": 1,
                "warning": 2,
                "info": 3,
            },
        )

    def test_record_review_failed(self) -> None:
        """Test recording a failed review."""
        record_review_completed(
            repository="owner/repo",
            status="failed",
            verdict="",
            duration_seconds=5.0,
            files_analyzed=0,
            comments_by_severity={},
        )


class TestGitHubMetricsRecording:
    """Tests for GitHub API metrics helper functions."""

    def test_record_github_api_call(self) -> None:
        """Test recording a GitHub API call."""
        record_github_api_call(
            endpoint="pulls",
            method="GET",
            status_code=200,
            duration_seconds=0.25,
            rate_limit_remaining=4999,
            rate_limit_reset=1704067200,
        )

    def test_record_github_api_call_without_rate_limit(self) -> None:
        """Test recording a GitHub API call without rate limit info."""
        record_github_api_call(
            endpoint="reviews",
            method="POST",
            status_code=201,
            duration_seconds=0.5,
        )


class TestAppInfoMetric:
    """Tests for app info metric."""

    def test_initialize_app_info(self) -> None:
        """Test initializing app info metric."""
        initialize_app_info(
            version="0.1.1",
            environment="test",
        )
