"""Data Processor Service - Aggregates sensor data with sliding window calculations."""

import time
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Data Processor Service", version="1.0.0")

# In-memory storage for sensor readings and aggregates
sensor_data: dict[str, list[dict]] = defaultdict(list)

# Sliding window size in seconds (default 5 minutes)
WINDOW_SIZE = 300


class SensorReading(BaseModel):
    device_id: str = Field(..., min_length=1)
    sensor_type: str = Field(..., min_length=1)
    value: float
    unit: str = Field(..., min_length=1)
    timestamp: Optional[float] = None


class ProcessResponse(BaseModel):
    status: str
    device_id: str
    readings_count: int


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "data-processor", "version": "1.0.0"}


def compute_aggregates(readings: list[dict]) -> dict:
    """Compute min, max, average over the current sliding window."""
    now = time.time()
    window_readings = [r for r in readings if now - r["timestamp"] <= WINDOW_SIZE]

    if not window_readings:
        return {"count": 0, "average": None, "min": None, "max": None, "window_seconds": WINDOW_SIZE}

    values = [r["value"] for r in window_readings]
    return {
        "count": len(values),
        "average": round(sum(values) / len(values), 4),
        "min": min(values),
        "max": max(values),
        "window_seconds": WINDOW_SIZE,
        "latest_timestamp": max(r["timestamp"] for r in window_readings),
    }


@app.post("/process", response_model=ProcessResponse)
async def process_data(reading: SensorReading):
    """Process incoming sensor data and update aggregates."""
    if reading.timestamp is None:
        reading.timestamp = time.time()

    record = reading.model_dump()
    sensor_data[reading.device_id].append(record)

    # Prune old readings outside the window
    now = time.time()
    sensor_data[reading.device_id] = [
        r for r in sensor_data[reading.device_id] if now - r["timestamp"] <= WINDOW_SIZE * 2
    ]

    return ProcessResponse(
        status="processed",
        device_id=reading.device_id,
        readings_count=len(sensor_data[reading.device_id]),
    )


@app.get("/aggregates/{device_id}")
async def get_aggregates(device_id: str):
    """Get aggregated data for a specific device."""
    if device_id not in sensor_data:
        raise HTTPException(status_code=404, detail=f"No data found for device '{device_id}'")

    readings = sensor_data[device_id]
    aggregates = compute_aggregates(readings)

    return {
        "device_id": device_id,
        "aggregates": aggregates,
        "total_readings_stored": len(readings),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
