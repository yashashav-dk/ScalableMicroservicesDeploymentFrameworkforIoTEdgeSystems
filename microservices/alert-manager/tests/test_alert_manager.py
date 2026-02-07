"""Tests for alert-manager service."""

import pytest
from fastapi.testclient import TestClient

from app import app, alerts, alert_rules


@pytest.fixture(autouse=True)
def clear_data():
    """Reset state before each test."""
    alerts.clear()
    alert_rules.clear()
    # Re-add defaults
    alert_rules.extend([
        {"id": "default-temp-high", "sensor_type": "temperature", "condition": "gt", "threshold": 40.0, "severity": "critical"},
        {"id": "default-temp-low", "sensor_type": "temperature", "condition": "lt", "threshold": -10.0, "severity": "warning"},
        {"id": "default-humidity-high", "sensor_type": "humidity", "condition": "gt", "threshold": 90.0, "severity": "warning"},
    ])
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "alert-manager"


def test_evaluate_triggers_alert(client):
    payload = {
        "device_id": "device-001",
        "sensor_type": "temperature",
        "value": 45.0,
        "timestamp": 1700000000.0,
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alerts_triggered"] == 1
    assert data["alerts"][0]["severity"] == "critical"


def test_evaluate_no_alert(client):
    payload = {
        "device_id": "device-001",
        "sensor_type": "temperature",
        "value": 22.0,
        "timestamp": 1700000000.0,
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alerts_triggered"] == 0


def test_get_alerts(client):
    # Trigger an alert first
    client.post("/evaluate", json={
        "device_id": "device-001",
        "sensor_type": "temperature",
        "value": 50.0,
        "timestamp": 1700000000.0,
    })
    response = client.get("/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_create_custom_rule(client):
    rule = {
        "sensor_type": "pressure",
        "condition": "gt",
        "threshold": 1050.0,
        "severity": "warning",
    }
    response = client.post("/rules", json=rule)
    assert response.status_code == 201
    data = response.json()
    assert data["sensor_type"] == "pressure"
    assert "id" in data
