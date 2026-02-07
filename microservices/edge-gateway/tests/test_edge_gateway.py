"""Tests for edge-gateway service."""

import pytest
from fastapi.testclient import TestClient

from app import app, rate_store, request_log, stats


@pytest.fixture(autouse=True)
def reset_state():
    """Reset gateway state before each test."""
    rate_store.clear()
    request_log.clear()
    stats["total_requests"] = 0
    stats["successful_proxies"] = 0
    stats["failed_proxies"] = 0
    stats["rate_limited"] = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "edge-gateway"
    assert data["version"] == "1.0.0"


def test_status_endpoint(client):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert "stats" in data
    assert "rate_limit" in data


def test_proxy_unknown_service(client):
    response = client.get("/api/v1/unknown-service/health")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_proxy_service_unavailable(client):
    """Test proxy when downstream service is not running."""
    response = client.get("/api/v1/device-registry/health")
    # Should get 502 since the service is not actually running
    assert response.status_code in (502, 500)


def test_status_tracks_requests(client):
    # Make some requests
    client.get("/api/v1/unknown-service/test")
    client.get("/api/v1/unknown-service/test2")

    response = client.get("/status")
    data = response.json()
    assert data["stats"]["total_requests"] == 2
