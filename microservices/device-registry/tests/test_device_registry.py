"""Tests for device-registry service."""

import pytest
from fastapi.testclient import TestClient

from app import app, devices


@pytest.fixture(autouse=True)
def clear_devices():
    """Clear device storage before each test."""
    devices.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "device-registry"


def test_register_device(client):
    payload = {
        "name": "Temperature Sensor A1",
        "device_type": "sensor",
        "location": "Building A, Floor 1",
    }
    response = client.post("/devices", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Temperature Sensor A1"
    assert data["device_type"] == "sensor"
    assert data["status"] == "active"
    assert "id" in data


def test_list_devices(client):
    client.post("/devices", json={"name": "Sensor 1", "device_type": "sensor"})
    client.post("/devices", json={"name": "Actuator 1", "device_type": "actuator"})

    response = client.get("/devices")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_get_device_by_id(client):
    create_resp = client.post("/devices", json={"name": "Sensor X", "device_type": "sensor"})
    device_id = create_resp.json()["id"]

    response = client.get(f"/devices/{device_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Sensor X"


def test_delete_device(client):
    create_resp = client.post("/devices", json={"name": "Temp", "device_type": "sensor"})
    device_id = create_resp.json()["id"]

    response = client.delete(f"/devices/{device_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    response = client.get(f"/devices/{device_id}")
    assert response.status_code == 404


def test_get_nonexistent_device(client):
    response = client.get("/devices/nonexistent")
    assert response.status_code == 404
