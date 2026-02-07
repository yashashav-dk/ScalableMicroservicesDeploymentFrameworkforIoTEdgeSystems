#!/usr/bin/env bash
# Integration test: starts docker-compose, runs end-to-end test sequence, tears down.
set -euo pipefail

COMPOSE_FILE="docker-compose.yaml"
MAX_WAIT=60
BASE_URL="http://localhost"

cleanup() {
    echo ""
    echo "--- Tearing down services ---"
    docker-compose -f "${COMPOSE_FILE}" down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "============================================"
echo "Integration Test Suite"
echo "============================================"

# Step 1: Start services
echo ""
echo "--- Starting services via docker-compose ---"
docker-compose -f "${COMPOSE_FILE}" up -d --build

# Step 2: Wait for all health checks
echo ""
echo "--- Waiting for services to become healthy ---"
SERVICES=("8001" "8002" "8003" "8004" "8005")
SERVICE_NAMES=("sensor-ingestion" "data-processor" "device-registry" "alert-manager" "edge-gateway")

for i in "${!SERVICES[@]}"; do
    port="${SERVICES[$i]}"
    name="${SERVICE_NAMES[$i]}"
    echo -n "Waiting for ${name} (port ${port})..."
    elapsed=0
    while [ ${elapsed} -lt ${MAX_WAIT} ]; do
        if curl -sf "${BASE_URL}:${port}/health" > /dev/null 2>&1; then
            echo " ready!"
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    if [ ${elapsed} -ge ${MAX_WAIT} ]; then
        echo " TIMEOUT!"
        echo "FAIL: ${name} did not become healthy within ${MAX_WAIT}s"
        exit 1
    fi
done

echo ""
echo "All services are healthy."

# Step 3: End-to-end test sequence
echo ""
echo "--- Running end-to-end test sequence ---"

# 3a. Register a device
echo "[1/5] Registering a test device..."
DEVICE_RESPONSE=$(curl -sf -X POST "${BASE_URL}:8003/devices" \
    -H "Content-Type: application/json" \
    -d '{"name": "Integration Test Sensor", "device_type": "sensor", "location": "Test Lab"}')
DEVICE_ID=$(echo "${DEVICE_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "  Device registered: ${DEVICE_ID}"

# 3b. Ingest sensor data
echo "[2/5] Ingesting sensor data..."
INGEST_RESPONSE=$(curl -sf -X POST "${BASE_URL}:8001/ingest" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\": \"${DEVICE_ID}\", \"sensor_type\": \"temperature\", \"value\": 45.5, \"unit\": \"celsius\"}")
echo "  Ingest response: ${INGEST_RESPONSE}"

# 3c. Process data directly
echo "[3/5] Processing sensor data..."
PROCESS_RESPONSE=$(curl -sf -X POST "${BASE_URL}:8002/process" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\": \"${DEVICE_ID}\", \"sensor_type\": \"temperature\", \"value\": 45.5, \"unit\": \"celsius\"}")
echo "  Process response: ${PROCESS_RESPONSE}"

# 3d. Evaluate for alerts (value 45.5 > default threshold 40)
echo "[4/5] Evaluating alerts..."
ALERT_RESPONSE=$(curl -sf -X POST "${BASE_URL}:8004/evaluate" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\": \"${DEVICE_ID}\", \"sensor_type\": \"temperature\", \"value\": 45.5}")
ALERTS_TRIGGERED=$(echo "${ALERT_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['alerts_triggered'])")
echo "  Alerts triggered: ${ALERTS_TRIGGERED}"

if [ "${ALERTS_TRIGGERED}" -lt 1 ]; then
    echo "FAIL: Expected at least 1 alert for temperature 45.5 > threshold 40"
    exit 1
fi

# 3e. Verify via edge gateway
echo "[5/5] Testing edge gateway proxy..."
GW_RESPONSE=$(curl -sf "${BASE_URL}:8005/api/v1/device-registry/devices")
TOTAL_DEVICES=$(echo "${GW_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])")
echo "  Devices via gateway: ${TOTAL_DEVICES}"

if [ "${TOTAL_DEVICES}" -lt 1 ]; then
    echo "FAIL: Expected at least 1 device via gateway"
    exit 1
fi

echo ""
echo "============================================"
echo "All integration tests PASSED"
echo "============================================"
