"""Tests for data-processor service."""

import time

import pytest
from fastapi.testclient import TestClient

from app import app, sensor_data


@pytest.fixture(autouse=True)
def clear_data():
    """Clear in-memory data before each test."""
    sensor_data.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "data-processor"
    assert data["version"] == "1.0.0"


def test_process_valid_reading(client):
    payload = {
        "device_id": "device-001",
        "sensor_type": "temperature",
        "value": 25.0,
        "unit": "celsius",
        "timestamp": time.time(),
    }
    response = client.post("/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["device_id"] == "device-001"
    assert data["readings_count"] == 1


def test_aggregates_after_multiple_readings(client):
    now = time.time()
    for val in [20.0, 25.0, 30.0]:
        client.post("/process", json={
            "device_id": "device-002",
            "sensor_type": "temperature",
            "value": val,
            "unit": "celsius",
            "timestamp": now,
        })

    response = client.get("/aggregates/device-002")
    assert response.status_code == 200
    data = response.json()
    assert data["aggregates"]["count"] == 3
    assert data["aggregates"]["average"] == 25.0
    assert data["aggregates"]["min"] == 20.0
    assert data["aggregates"]["max"] == 30.0


def test_aggregates_device_not_found(client):
    response = client.get("/aggregates/nonexistent")
    assert response.status_code == 404
    assert "No data found" in response.json()["detail"]


def test_process_missing_fields(client):
    response = client.post("/process", json={"device_id": "d1"})
    assert response.status_code == 422
