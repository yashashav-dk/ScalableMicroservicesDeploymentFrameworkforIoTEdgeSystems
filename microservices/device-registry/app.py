"""Device Registry Service - Manages IoT device metadata with in-memory storage."""

import uuid
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Device Registry Service", version="1.0.0")

# In-memory device storage
devices: dict[str, dict] = {}


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, description="e.g., sensor, actuator, gateway")
    location: Optional[str] = None
    metadata: Optional[dict] = None


class DeviceResponse(BaseModel):
    id: str
    name: str
    device_type: str
    location: Optional[str]
    metadata: Optional[dict]
    registered_at: float
    status: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "device-registry", "version": "1.0.0"}


@app.post("/devices", response_model=DeviceResponse, status_code=201)
async def register_device(device: DeviceCreate):
    """Register a new IoT device."""
    device_id = str(uuid.uuid4())[:8]
    record = {
        "id": device_id,
        "name": device.name,
        "device_type": device.device_type,
        "location": device.location,
        "metadata": device.metadata or {},
        "registered_at": time.time(),
        "status": "active",
    }
    devices[device_id] = record
    return DeviceResponse(**record)


@app.get("/devices")
async def list_devices(device_type: Optional[str] = None, status: Optional[str] = None):
    """List all registered devices with optional filtering."""
    result = list(devices.values())

    if device_type:
        result = [d for d in result if d["device_type"] == device_type]
    if status:
        result = [d for d in result if d["status"] == status]

    return {"devices": result, "total": len(result)}


@app.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    """Look up a specific device by ID."""
    if device_id not in devices:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return DeviceResponse(**devices[device_id])


@app.delete("/devices/{device_id}")
async def deregister_device(device_id: str):
    """Deregister (remove) a device."""
    if device_id not in devices:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    del devices[device_id]
    return {"status": "deleted", "device_id": device_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
