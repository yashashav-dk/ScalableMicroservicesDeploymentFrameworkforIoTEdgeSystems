#!/usr/bin/env bash
# Run pytest with coverage for each microservice.
set -euo pipefail

SERVICES=("sensor-ingestion" "data-processor" "device-registry" "alert-manager" "edge-gateway")
FAILED=0

echo "============================================"
echo "Running unit tests for all services"
echo "============================================"

for service in "${SERVICES[@]}"; do
    echo ""
    echo "--- Testing ${service} ---"
    cd "microservices/${service}"

    pip install -r requirements.txt --quiet 2>/dev/null

    if python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing; then
        echo "✓ ${service} tests PASSED"
    else
        echo "✗ ${service} tests FAILED"
        FAILED=$((FAILED + 1))
    fi

    cd ../..
done

echo ""
echo "============================================"
if [ ${FAILED} -eq 0 ]; then
    echo "All tests passed!"
    exit 0
else
    echo "${FAILED} service(s) had test failures"
    exit 1
fi
