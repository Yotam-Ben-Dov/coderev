"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test the health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_ready_endpoint(self, client: TestClient) -> None:
        """Test the readiness endpoint."""
        response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ready", "not_ready")
        assert "checks" in data


class TestReviewEndpoints:
    """Tests for review endpoints."""

    def test_trigger_review_validation(self, client: TestClient) -> None:
        """Test that review endpoint validates input."""
        # Missing required fields
        response = client.post("/reviews", json={})
        assert response.status_code == 422

        # Invalid PR number
        response = client.post(
            "/reviews",
            json={
                "owner": "test",
                "repo": "repo",
                "pr_number": -1,  # Invalid
            },
        )
        assert response.status_code == 422

    def test_get_nonexistent_review(self, client: TestClient) -> None:
        """Test getting a review that doesn't exist."""
        response = client.get("/reviews/99999")
        assert response.status_code == 404

    def test_get_task_status_nonexistent(self, client: TestClient) -> None:
        """Test getting status of nonexistent task."""
        response = client.get("/reviews/tasks/nonexistent-task-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"  # Celery returns PENDING for unknown tasks


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    def test_webhook_ping(self, client: TestClient) -> None:
        """Test GitHub ping event."""
        response = client.post(
            "/webhooks/github",
            json={"zen": "Test zen message"},
            headers={"X-GitHub-Event": "ping"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "pong"

    def test_webhook_unhandled_event(self, client: TestClient) -> None:
        """Test unhandled webhook event."""
        response = client.post(
            "/webhooks/github",
            json={"action": "created"},
            headers={"X-GitHub-Event": "issue_comment"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] is False

    def test_webhook_missing_event_header(self, client: TestClient) -> None:
        """Test webhook without event header."""
        response = client.post(
            "/webhooks/github",
            json={"action": "opened"},
        )
        
        assert response.status_code == 422  # Missing required header

    def test_webhook_health(self, client: TestClient) -> None:
        """Test webhook health endpoint."""
        response = client.get("/webhooks/github/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"