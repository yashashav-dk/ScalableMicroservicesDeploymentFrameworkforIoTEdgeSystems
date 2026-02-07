"""Edge Gateway Service - API gateway with rate limiting and request proxying."""

import os
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Edge Gateway Service", version="1.0.0")

# Service discovery via environment variables
SERVICE_MAP = {
    "sensor-ingestion": os.getenv("SENSOR_INGESTION_URL", "http://localhost:8001"),
    "data-processor": os.getenv("DATA_PROCESSOR_URL", "http://localhost:8002"),
    "device-registry": os.getenv("DEVICE_REGISTRY_URL", "http://localhost:8003"),
    "alert-manager": os.getenv("ALERT_MANAGER_URL", "http://localhost:8004"),
}

# Rate limiting: max requests per IP per window
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "60"))

# Rate limiter storage: {ip: [(timestamp, ...),]}
rate_store: dict[str, list[float]] = defaultdict(list)

# Request log
request_log: list[dict] = []
MAX_LOG_SIZE = 1000

# Stats
stats = {
    "total_requests": 0,
    "successful_proxies": 0,
    "failed_proxies": 0,
    "rate_limited": 0,
    "start_time": time.time(),
}


def check_rate_limit(client_ip: str) -> bool:
    """Check if the client IP has exceeded the rate limit."""
    now = time.time()
    # Prune old entries
    rate_store[client_ip] = [t for t in rate_store[client_ip] if now - t < RATE_WINDOW]
    if len(rate_store[client_ip]) >= RATE_LIMIT:
        return False
    rate_store[client_ip].append(now)
    return True


def log_request(method: str, path: str, client_ip: str, status_code: int, duration_ms: float):
    """Log a request for monitoring."""
    entry = {
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "timestamp": time.time(),
    }
    request_log.append(entry)
    if len(request_log) > MAX_LOG_SIZE:
        request_log.pop(0)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "edge-gateway", "version": "1.0.0"}


@app.get("/status")
async def status():
    uptime = time.time() - stats["start_time"]
    return {
        "services": {name: url for name, url in SERVICE_MAP.items()},
        "stats": {
            "total_requests": stats["total_requests"],
            "successful_proxies": stats["successful_proxies"],
            "failed_proxies": stats["failed_proxies"],
            "rate_limited": stats["rate_limited"],
            "uptime_seconds": round(uptime, 2),
        },
        "rate_limit": {"max_requests": RATE_LIMIT, "window_seconds": RATE_WINDOW},
        "recent_requests": len(request_log),
    }


@app.api_route("/api/v1/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(service: str, path: str, request: Request):
    """Proxy requests to downstream microservices."""
    start = time.time()
    client_ip = request.client.host if request.client else "unknown"
    stats["total_requests"] += 1

    # Rate limiting
    if not check_rate_limit(client_ip):
        stats["rate_limited"] += 1
        log_request(request.method, f"/api/v1/{service}/{path}", client_ip, 429, 0)
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    # Resolve service
    if service not in SERVICE_MAP:
        log_request(request.method, f"/api/v1/{service}/{path}", client_ip, 404, 0)
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found. Available: {list(SERVICE_MAP.keys())}")

    target_url = f"{SERVICE_MAP[service]}/{path}"

    try:
        body = await request.body()
        headers = {
            "content-type": request.headers.get("content-type", "application/json"),
            "x-forwarded-for": client_ip,
            "x-gateway-request-id": f"gw-{int(time.time() * 1000)}",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )

        duration_ms = (time.time() - start) * 1000
        stats["successful_proxies"] += 1
        log_request(request.method, f"/api/v1/{service}/{path}", client_ip, response.status_code, duration_ms)

        return JSONResponse(
            content=response.json(),
            status_code=response.status_code,
        )
    except httpx.ConnectError:
        duration_ms = (time.time() - start) * 1000
        stats["failed_proxies"] += 1
        log_request(request.method, f"/api/v1/{service}/{path}", client_ip, 502, duration_ms)
        raise HTTPException(status_code=502, detail=f"Service '{service}' is unavailable")
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        stats["failed_proxies"] += 1
        log_request(request.method, f"/api/v1/{service}/{path}", client_ip, 500, duration_ms)
        raise HTTPException(status_code=500, detail=f"Gateway error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
