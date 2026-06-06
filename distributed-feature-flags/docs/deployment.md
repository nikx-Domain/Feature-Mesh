# Platform Deployment Guide

This guide describes the complete deployment architecture and local development experience for the Distributed Feature Flag Platform.

## Architecture

The deployment architecture utilizes Docker Compose to run a full multi-container application locally, simulating a production-like environment without Kubernetes.

### Components
1. **API Service**: The core FastAPI backend handling all REST traffic.
2. **PostgreSQL**: The primary database storing feature flags, tenants, users, and environments.
3. **Redis**: Cache layer for real-time flag evaluations and fallback storage.
4. **Zookeeper & Kafka**: Event streaming for audit logs and cache invalidations using the transactional outbox pattern.
5. **Prometheus & Grafana**: Integrated observability stack for scraping API metrics and visualizing performance.
6. **Kafka UI**: Graphical interface for exploring Kafka topics, consumers, and data.

---

## Local Development Experience

To start the platform from scratch, simply run the following steps:

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd distributed-feature-flags
   ```

2. **Configure Environment**
   Copy the example environment variables:
   ```bash
   cp .env.example .env
   ```
   *(Update any passwords or secret keys in `.env` if this is a production-like environment.)*

3. **Start the Stack**
   ```bash
   docker compose up -d
   ```
   *The `docker-compose.yml` ensures correct startup ordering. The API will wait for PostgreSQL, Redis, and Kafka to be healthy before accepting traffic.*

4. **Verify Deployment**
   Run the verification script to ensure all services are healthy:
   ```bash
   ./scripts/verify_deployment.sh
   ```

---

## Accessing Services

Once the stack is running, you can access the various services at the following local URLs:

| Service | Address | Description |
|---|---|---|
| **API** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for exploring the REST API |
| **Health (Live)** | [http://localhost:8000/health/live](http://localhost:8000/health/live) | Liveness probe (Process level) |
| **Health (Ready)** | [http://localhost:8000/health/ready](http://localhost:8000/health/ready) | Readiness probe (Dependencies level) |
| **Grafana** | [http://localhost:3000](http://localhost:3000) | Observability dashboards (Auto-logs in via config) |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | Time-series metrics datastore and queries |
| **Kafka UI** | [http://localhost:8080](http://localhost:8080) | Explore Kafka Topics and Consumer Groups |

---

## Persistent Storage Configuration

The `docker-compose.yml` mounts named volumes to ensure that no data is lost upon container restart.

- `postgres_data`: Persists DB data.
- `redis_data`: Persists cache state (via RDB snapshots).
- `kafka_data` & `zookeeper_data`: Persists event streams.
- `prometheus_data`: Persists timeseries metrics.
- `grafana_data`: Persists user-defined dashboard changes (default dashboards are auto-provisioned).

---

## Operational Runbooks

Please refer to the detailed operational runbooks inside `docs/runbooks/` for:
- [Startup & Shutdown Procedures](./runbooks/startup.md)
- [Backup Strategy](./runbooks/backup.md)
- [Troubleshooting Common Issues](./runbooks/troubleshooting.md)
