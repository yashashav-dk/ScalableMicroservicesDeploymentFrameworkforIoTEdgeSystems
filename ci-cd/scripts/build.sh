#!/usr/bin/env bash
# Build Docker images for all microservices with git SHA tagging.
set -euo pipefail

REGISTRY="${DOCKER_REGISTRY:-localhost:5000}"
GIT_SHA=$(git rev-parse --short HEAD)
SERVICES=("sensor-ingestion" "data-processor" "device-registry" "alert-manager" "edge-gateway")

echo "============================================"
echo "Building Docker images"
echo "Registry: ${REGISTRY}"
echo "Git SHA:  ${GIT_SHA}"
echo "============================================"

for service in "${SERVICES[@]}"; do
    echo ""
    echo "--- Building ${service} ---"
    docker build \
        -t "${REGISTRY}/${service}:${GIT_SHA}" \
        -t "${REGISTRY}/${service}:latest" \
        "microservices/${service}/"
    echo "✓ Built ${service}:${GIT_SHA}"
done

echo ""
echo "============================================"
echo "All images built successfully"
echo "============================================"
docker images | grep "${GIT_SHA}" || true
