"""Alert Manager Service - Evaluates sensor data against configurable thresholds."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# In-memory storage
alert_rules: list[dict] = []
alerts: list[dict] = []

# Default rules
DEFAULT_RULES = [
    {"id": "default-temp-high", "sensor_type": "temperature", "condition": "gt", "threshold": 40.0, "severity": "critical"},
    {"id": "default-temp-low", "sensor_type": "temperature", "condition": "lt", "threshold": -10.0, "severity": "warning"},
    {"id": "default-humidity-high", "sensor_type": "humidity", "condition": "gt", "threshold": 90.0, "severity": "warning"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    alert_rules.extend(DEFAULT_RULES)
    yield


app = FastAPI(title="Alert Manager Service", version="1.0.0", lifespan=lifespan)


class AlertRule(BaseModel):
    sensor_type: str = Field(..., min_length=1)
    condition: str = Field(..., pattern="^(gt|lt|gte|lte|eq)$")
    threshold: float
    severity: str = Field(default="warning", pattern="^(info|warning|critical)$")


class EvaluateRequest(BaseModel):
    device_id: str = Field(..., min_length=1)
    sensor_type: str = Field(..., min_length=1)
    value: float
    timestamp: Optional[float] = None


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "alert-manager", "version": "1.0.0"}


def check_condition(value: float, condition: str, threshold: float) -> bool:
    """Evaluate a condition against a threshold."""
    ops = {
        "gt": lambda v, t: v > t,
        "lt": lambda v, t: v < t,
        "gte": lambda v, t: v >= t,
        "lte": lambda v, t: v <= t,
        "eq": lambda v, t: v == t,
    }
    return ops[condition](value, threshold)


@app.post("/evaluate")
async def evaluate_data(request: EvaluateRequest):
    """Evaluate sensor data against alert rules."""
    if request.timestamp is None:
        request.timestamp = time.time()

    triggered = []
    matching_rules = [r for r in alert_rules if r["sensor_type"] == request.sensor_type]

    for rule in matching_rules:
        if check_condition(request.value, rule["condition"], rule["threshold"]):
            alert = {
                "id": str(uuid.uuid4())[:8],
                "rule_id": rule["id"],
                "device_id": request.device_id,
                "sensor_type": request.sensor_type,
                "value": request.value,
                "threshold": rule["threshold"],
                "condition": rule["condition"],
                "severity": rule["severity"],
                "triggered_at": request.timestamp,
                "message": f"Alert: {request.sensor_type} value {request.value} {rule['condition']} threshold {rule['threshold']}",
            }
            alerts.append(alert)
            triggered.append(alert)

    return {
        "device_id": request.device_id,
        "rules_evaluated": len(matching_rules),
        "alerts_triggered": len(triggered),
        "alerts": triggered,
    }


@app.get("/alerts")
async def get_alerts(
    device_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
):
    """Retrieve alerts with optional filtering."""
    result = list(alerts)

    if device_id:
        result = [a for a in result if a["device_id"] == device_id]
    if severity:
        result = [a for a in result if a["severity"] == severity]

    result = sorted(result, key=lambda x: x["triggered_at"], reverse=True)[:limit]
    return {"alerts": result, "total": len(result)}


@app.post("/rules", status_code=201)
async def create_rule(rule: AlertRule):
    """Create a new alert rule."""
    rule_record = {
        "id": str(uuid.uuid4())[:8],
        **rule.model_dump(),
    }
    alert_rules.append(rule_record)
    return rule_record


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
