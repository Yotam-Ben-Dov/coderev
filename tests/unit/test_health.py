from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test the health check endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_readiness_check(client: TestClient) -> None:
    """Test the readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ("ready", "not_ready")
    assert "checks" in data