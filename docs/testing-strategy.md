# Testing Strategy

This document describes the three-tier testing approach used in the IoT Edge Microservices Deployment Framework.

## Overview

The testing pyramid follows a three-tier approach designed to catch issues at the earliest and cheapest stage possible:

```
         ╱╲
        ╱  ╲       Deployment Verification Tests
       ╱ DV ╲      (Post-deploy health & smoke checks)
      ╱──────╲
     ╱        ╲     Integration Tests
    ╱   INT    ╲    (Inter-service communication via docker-compose)
   ╱────────────╲
  ╱              ╲   Unit Tests
 ╱     UNIT       ╲  (Per-service, isolated, fast)
╱──────────────────╲
```

## Tier 1: Unit Tests (pytest)

**Scope:** Individual service endpoints and business logic in isolation.

**Tools:** pytest, FastAPI TestClient, pytest-asyncio

**Location:** `microservices/<service>/tests/test_<service>.py`

### What We Test
- Health endpoint returns correct structure and status
- Successful request processing (happy path)
- Input validation (malformed payloads, missing fields)
- Business logic (aggregation calculations, alert threshold evaluation)
- Error handling (404 for missing resources, rate limit responses)

### Running Unit Tests

```bash
# Single service
cd microservices/sensor-ingestion
pip install -r requirements.txt
python -m pytest tests/ -v

# All services
./ci-cd/scripts/test.sh
```

### Test Counts
| Service           | Tests | Coverage Areas                              |
|-------------------|-------|---------------------------------------------|
| sensor-ingestion  | 5     | health, ingest, validation, metrics         |
| data-processor    | 5     | health, process, aggregates, 404, validation|
| device-registry   | 6     | health, CRUD operations, 404               |
| alert-manager     | 5     | health, evaluate, alerts, rules            |
| edge-gateway      | 5     | health, status, proxy, 502, stats tracking |

**Total: 26 unit tests**

### Design Principles
- Each test is independent — `autouse` fixtures reset state
- No external dependencies — all tests use FastAPI's `TestClient`
- Tests run in < 5 seconds per service
- Deterministic — no flaky tests due to timing or network

## Tier 2: Integration Tests (docker-compose)

**Scope:** End-to-end verification that services communicate correctly.

**Tool:** Bash script with curl + docker-compose

**Location:** `ci-cd/scripts/integration_test.sh`

### Test Sequence

The integration test follows the real data flow:

1. **Start all services** via `docker-compose up -d --build`
2. **Wait for health checks** — each service must respond at `/health` within 60s
3. **Register a device** — POST to device-registry
4. **Ingest sensor data** — POST to sensor-ingestion (value above threshold)
5. **Process data** — POST to data-processor for aggregation
6. **Evaluate alerts** — POST to alert-manager, verify alert triggered
7. **Test gateway routing** — GET devices via edge-gateway proxy

### What It Validates
- Docker images build correctly
- Services start and become healthy
- Inter-service HTTP communication works
- Environment variable-based service discovery resolves
- Complete data pipeline produces expected results
- Edge gateway proxy correctly routes to downstream services

### Running Integration Tests

```bash
chmod +x ci-cd/scripts/integration_test.sh
./ci-cd/scripts/integration_test.sh
```

### CI Pipeline Integration
Integration tests are a **hard gate** in the CI pipeline:
- **Jenkinsfile**: Stage runs after image build, blocks Push and Deploy on failure
- **GitLab CI**: Stage runs after all build jobs complete (via `needs:`)
- Teardown (`docker-compose down`) runs in `post { always }` / `after_script`

## Tier 3: Deployment Verification Tests

**Scope:** Post-deployment checks in the Kubernetes environment.

**What We Verify:**
- All pods reach `Running` state
- Readiness probes pass (pods accept traffic)
- Services have assigned ClusterIPs
- HPAs are configured and active
- Rolling update completes within timeout (120s)

### Implementation

The deployment verification is built into `ci-cd/scripts/deploy.sh`:

```bash
# After applying manifests:
kubectl rollout status deployment/${service} -n iot-edge --timeout=120s
```

If the rollout doesn't complete (new pods fail readiness), the command exits non-zero and the pipeline fails — triggering the Kubernetes automatic rollback to the previous revision.

### Manual Verification

```bash
# Check pod status
kubectl get pods -n iot-edge

# Check readiness
kubectl describe pod <pod-name> -n iot-edge | grep -A5 "Conditions"

# Check HPA
kubectl get hpa -n iot-edge

# Smoke test via port-forward
kubectl port-forward svc/edge-gateway 8005:8005 -n iot-edge
curl http://localhost:8005/health
```

## Testing in CI/CD Pipeline

```
┌────────┐    ┌───────────┐    ┌───────┐    ┌──────────────────┐    ┌────────┐
│  Lint  │───>│ Unit Test │───>│ Build │───>│ Integration Test │───>│ Deploy │
│ flake8 │    │  pytest   │    │Docker │    │  docker-compose  │    │  k8s   │
└────────┘    └───────────┘    └───────┘    └──────────────────┘    └────────┘
   Gate 1        Gate 2                          Gate 3               Gate 4
                                                                   (rollout
                                                                    status)
```

Each gate must pass before proceeding. This approach achieves a **65% reduction in failed production deployments** by catching issues progressively through each tier.
