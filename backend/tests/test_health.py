"""Tests for GET /health endpoint."""
from fastapi.testclient import TestClient


def test_health_endpoint_success(client: TestClient):
    """Verify that /health returns HTTP 200 with required fields."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert data["app"] == "RecoverAI"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "database" in data
    assert "status" in data["database"]
    assert "razorpay_mode" in data
    assert data["razorpay_mode"] == "test"


def test_root_endpoint_success(client: TestClient):
    """Verify that / root endpoint returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["service"] == "RecoverAI"
    assert data["health"] == "/health"
