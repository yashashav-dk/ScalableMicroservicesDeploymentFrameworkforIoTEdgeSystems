#!/usr/bin/env bash
# Deploy microservices to Kubernetes with rolling update strategy.
set -euo pipefail

GIT_SHA="${1:-latest}"
NAMESPACE="iot-edge"
REGISTRY="${DOCKER_REGISTRY:-localhost:5000}"
SERVICES=("sensor-ingestion" "data-processor" "device-registry" "alert-manager" "edge-gateway")

echo "============================================"
echo "Deploying to Kubernetes"
echo "Namespace: ${NAMESPACE}"
echo "Image tag: ${GIT_SHA}"
echo "============================================"

# Ensure namespace exists
echo ""
echo "--- Applying namespace ---"
kubectl apply -f kubernetes/namespace.yaml

# Deploy each service
for service in "${SERVICES[@]}"; do
    echo ""
    echo "--- Deploying ${service} ---"

    # Apply manifests
    kubectl apply -f "kubernetes/${service}/deployment.yaml"
    kubectl apply -f "kubernetes/${service}/service.yaml"
    kubectl apply -f "kubernetes/${service}/hpa.yaml"

    # Update image tag for rolling update
    kubectl set image "deployment/${service}" \
        "${service}=${REGISTRY}/${service}:${GIT_SHA}" \
        -n "${NAMESPACE}"

    echo "  Waiting for rollout..."
    kubectl rollout status "deployment/${service}" -n "${NAMESPACE}" --timeout=120s

    echo "  ✓ ${service} deployed successfully"
done

echo ""
echo "============================================"
echo "Deployment complete!"
echo "============================================"

# Show final status
echo ""
echo "--- Pod Status ---"
kubectl get pods -n "${NAMESPACE}" -o wide

echo ""
echo "--- Service Status ---"
kubectl get services -n "${NAMESPACE}"
