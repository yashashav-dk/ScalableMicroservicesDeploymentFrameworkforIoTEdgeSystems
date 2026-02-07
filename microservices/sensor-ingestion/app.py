"""Sensor Ingestion Service - Receives IoT sensor data and forwards to data-processor."""

import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Sensor Ingestion Service", version="1.0.0")

# Configuration
DATA_PROCESSOR_URL = os.getenv("DATA_PROCESSOR_URL", "http://localhost:8002")

# Metrics storage
metrics = {
    "total_ingested": 0,
    "successful_forwards": 0,
    "failed_forwards": 0,
    "invalid_payloads": 0,
    "start_time": time.time(),
}


class SensorReading(BaseModel):
    device_id: str = Field(..., min_length=1, description="Unique device identifier")
    sensor_type: str = Field(..., min_length=1, description="Type of sensor (temperature, humidity, pressure)")
    value: float = Field(..., description="Sensor reading value")
    unit: str = Field(..., min_length=1, description="Measurement unit")
    timestamp: Optional[float] = Field(default=None, description="Unix timestamp of reading")


class IngestResponse(BaseModel):
    status: str
    message: str
    device_id: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sensor-ingestion", "version": "1.0.0"}


@app.get("/metrics")
async def get_metrics():
    uptime = time.time() - metrics["start_time"]
    return {
        "total_ingested": metrics["total_ingested"],
        "successful_forwards": metrics["successful_forwards"],
        "failed_forwards": metrics["failed_forwards"],
        "invalid_payloads": metrics["invalid_payloads"],
        "uptime_seconds": round(uptime, 2),
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_sensor_data(reading: SensorReading):
    """Receive sensor data, validate, and forward to data-processor."""
    if reading.timestamp is None:
        reading.timestamp = time.time()

    metrics["total_ingested"] += 1

    # Validate sensor type
    valid_types = {"temperature", "humidity", "pressure", "light", "motion", "co2"}
    if reading.sensor_type.lower() not in valid_types:
        metrics["invalid_payloads"] += 1
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sensor_type '{reading.sensor_type}'. Must be one of: {', '.join(sorted(valid_types))}",
        )

    # Forward to data-processor
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{DATA_PROCESSOR_URL}/process",
                json=reading.model_dump(),
            )
            response.raise_for_status()
            metrics["successful_forwards"] += 1
    except Exception:
        metrics["failed_forwards"] += 1
        # Still accept the data even if forwarding fails
        return IngestResponse(
            status="accepted_with_warning",
            message="Data ingested but forwarding to processor failed",
            device_id=reading.device_id,
        )

    return IngestResponse(
        status="accepted",
        message="Data ingested and forwarded successfully",
        device_id=reading.device_id,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
