"""Tests for sensor-ingestion service."""

import pytest
from fastapi.testclient import TestClient

from app import app, metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test."""
    metrics["total_ingested"] = 0
    metrics["successful_forwards"] = 0
    metrics["failed_forwards"] = 0
    metrics["invalid_payloads"] = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "sensor-ingestion"
    assert data["version"] == "1.0.0"


def test_ingest_valid_sensor_data(client):
    payload = {
        "device_id": "device-001",
        "sensor_type": "temperature",
        "value": 23.5,
        "unit": "celsius",
        "timestamp": 1700000000.0,
    }
    response = client.post("/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "device-001"
    assert data["status"] in ("accepted", "accepted_with_warning")


def test_ingest_invalid_sensor_type(client):
    payload = {
        "device_id": "device-001",
        "sensor_type": "invalid_type",
        "value": 23.5,
        "unit": "celsius",
    }
    response = client.post("/ingest", json=payload)
    assert response.status_code == 400
    assert "Invalid sensor_type" in response.json()["detail"]


def test_ingest_missing_required_fields(client):
    payload = {"device_id": "device-001"}
    response = client.post("/ingest", json=payload)
    assert response.status_code == 422


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_ingested" in data
    assert "uptime_seconds" in data
    assert data["total_ingested"] == 0
