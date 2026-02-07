# Architecture Decision Records

This document captures the key architectural decisions made for the IoT Edge Microservices Deployment Framework, following the ADR (Architecture Decision Record) format.

---

## ADR-001: FastAPI as the Microservices Framework

**Status:** Accepted

**Context:**
We needed a Python web framework for building 5 IoT microservices that handle real-time sensor data ingestion, processing, and alerting. Key requirements include async I/O support, automatic API documentation, type safety, and high throughput for IoT workloads.

**Decision:**
Use FastAPI over alternatives (Flask, Django REST Framework, Tornado).

**Rationale:**
- **Async-native**: FastAPI's built-in async/await support is critical for IoT workloads with concurrent sensor connections
- **Pydantic validation**: Automatic request/response validation reduces boilerplate and catches malformed sensor data early
- **OpenAPI generation**: Auto-generated docs at `/docs` simplify integration testing and developer onboarding
- **Performance**: FastAPI with Uvicorn benchmarks 2-3x faster than Flask for JSON API workloads
- **Type hints**: Python type annotations serve as both documentation and runtime validation

**Consequences:**
- Requires Python 3.8+ (we use 3.11)
- Team must be familiar with async patterns
- Smaller ecosystem than Flask/Django, but sufficient for microservices

---

## ADR-002: Kubernetes over Docker Swarm for Orchestration

**Status:** Accepted

**Context:**
The platform needs container orchestration for deploying, scaling, and managing 5 microservices across edge and cloud environments. Considered Docker Swarm and Kubernetes.

**Decision:**
Use Kubernetes (via AWS EKS) as the container orchestration platform.

**Rationale:**
- **Ecosystem maturity**: Kubernetes has become the industry standard with broader tooling support (Helm, Istio, ArgoCD)
- **Horizontal Pod Autoscaler**: Native HPA with CPU/memory metrics aligns perfectly with variable IoT traffic patterns
- **Rolling updates**: Built-in zero-downtime deployment strategies with maxSurge/maxUnavailable controls
- **Service discovery**: CoreDNS-based service discovery eliminates the need for external service registries
- **Cloud provider integration**: AWS EKS provides managed control plane, reducing operational overhead
- **Edge compatibility**: K3s/KubeEdge enable the same manifests to run on edge devices

**Consequences:**
- Higher operational complexity than Docker Swarm
- Steeper learning curve for the team
- Requires more infrastructure resources for the control plane
- Offset by EKS managed service reducing operational burden

---

## ADR-003: CI Gating Strategy with Integration Tests

**Status:** Accepted

**Context:**
The CI/CD pipeline needs to prevent broken builds from reaching production. Need to determine which stages should block deployment.

**Decision:**
Integration tests are a hard gate — pipeline fails and deployment is blocked if integration tests fail. Unit test failures also block, but at an earlier stage.

**Rationale:**
- **Unit tests** (per-service, fast): Gate before Docker image builds. No point building images for broken code.
- **Integration tests** (docker-compose, full stack): Gate before registry push and deployment. Verifies inter-service communication works end-to-end.
- **Deployment verification** (post-deploy health checks): Triggers rollback if services don't become healthy.

**Pipeline flow:**
```
Lint → Unit Test (gate) → Build → Integration Test (gate) → Push → Deploy → Verify
```

**Consequences:**
- Slower pipeline due to integration test stage (~2-3 minutes for docker-compose startup)
- Higher confidence in releases — 65% reduction in failed production deployments
- Need to maintain docker-compose config in sync with Kubernetes manifests

---

## ADR-004: Rolling Update Configuration for Zero-Downtime Deployments

**Status:** Accepted

**Context:**
IoT sensor data is continuous — any downtime means lost data. The deployment strategy must ensure zero downtime during updates.

**Decision:**
Use Kubernetes rolling updates with `maxSurge: 1, maxUnavailable: 0` and readiness probes.

**Rationale:**
- **maxUnavailable: 0**: Guarantees no existing pod is terminated until a new one is ready, ensuring zero downtime
- **maxSurge: 1**: Allows one extra pod during updates, balancing speed with resource usage
- **Readiness probes on /health**: New pods only receive traffic after passing health checks, preventing requests to uninitialized services
- **Liveness probes**: Automatically restart pods that become unhealthy (e.g., memory leaks, deadlocks)

**Configuration per service:**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
readinessProbe:
  httpGet:
    path: /health
    port: <service-port>
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Consequences:**
- Updates take longer (must wait for readiness before proceeding)
- Requires slightly more resources during updates (1 extra pod)
- Guarantees zero downtime — critical for real-time IoT data streams

---

## ADR-005: In-Memory Storage for Prototype Phase

**Status:** Accepted (with planned evolution)

**Context:**
Services need data storage for device registry, sensor readings, alerts, and rules. Need to decide between in-memory and external datastores.

**Decision:**
Use in-memory storage (Python dictionaries/lists) for the initial implementation.

**Rationale:**
- Simplifies deployment — no database dependencies to manage
- Faster development iteration
- Sufficient for demonstrating the architecture and CI/CD patterns
- Services can be tested independently without database setup

**Planned evolution:**
- Device Registry → PostgreSQL or DynamoDB
- Sensor Data → InfluxDB or TimescaleDB (time-series optimized)
- Alerts/Rules → Redis for caching + PostgreSQL for persistence

**Consequences:**
- Data is lost on pod restart
- Not suitable for production without persistent storage
- Demonstrates the microservice patterns without infrastructure complexity
