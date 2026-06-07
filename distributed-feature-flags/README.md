# Distributed Feature Flag Platform

A production-grade, highly scalable, and distributed control plane for managing feature flags across complex microservice environments. 

## Problem Statement

As engineering teams scale, the ability to decouple deployment from release becomes critical. Feature flags enable dark launching, A/B testing, and targeted rollouts. However, building a feature flag system that is performant (sub-millisecond evaluation), highly available, and consistent across distributed clusters is a massive engineering challenge. 

This platform solves that by providing a robust, tenant-aware, event-driven feature flag control plane.

## Architecture Highlights

This platform is built around **Clean Architecture**, **Domain-Driven Design (DDD)**, and **Event-Driven Architecture (EDA)**.

- **FastAPI / AsyncIO**: Provides high-throughput, low-latency API handling.
- **PostgreSQL**: Serves as the persistent source of truth, protected by the **Unit of Work** pattern.
- **Redis Cache**: Ensures sub-millisecond evaluation latency.
- **Kafka & Outbox Pattern**: Guarantees zero-loss event streaming. Changes to feature flags are asynchronously broadcasted to consumers for cache invalidation and audit logging.
- **Circuit Breakers**: Protects backend dependencies from cascading failures.

[View full Architecture Diagrams here](docs/architecture/system_architecture.md).

## Core Features

- **Multi-Tenancy**: Complete logical isolation via Organizations and Projects.
- **Advanced Targeting**: Percentage-based rollouts (deterministic hashing), multi-attribute evaluation rules.
- **Event-Driven Resilience**: Transactional outbox pattern prevents dual-write problems.
- **Dead Letter Queue (DLQ)**: Kafka consumers feature exponential backoff and DLQ routing.
- **Security First**: RS256 JWT Auth, Refresh Token Rotation, Rate Limiting, and strict security headers.
- **Observability**: Built-in Prometheus metrics and Grafana dashboards.

## Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic
- **Data & Streaming**: PostgreSQL (asyncpg), Redis, Apache Kafka
- **Resilience**: Pybreaker, Slowapi
- **Observability**: Prometheus, Grafana, Structlog
- **Infrastructure**: Docker, Docker Compose

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Populate passwords and keys in .env
```

### 2. Boot the Platform
The platform relies on Docker Compose to orchestrate the API, Postgres, Redis, Kafka, and Observability stack. Database migrations are executed automatically on boot.

```bash
docker compose up --build -d
```

### 3. Verify Health
```bash
curl http://localhost:8000/health/live
```

## Documentation

- [Production Readiness Report](docs/final_production_readiness.md)
- [Backup & Restore Guide](docs/backup_restore_validation.md)
- [Database Schema Review](docs/database_hardening_review.md)
- [System Architecture](docs/architecture/system_architecture.md)

## Future Work

- **Kubernetes Manifests**: Helm charts for K8s deployment.
- **Client SDKs**: Native Go, Java, and TypeScript SDKs using Server-Sent Events (SSE) for real-time flag updates.
- **Partitioning**: Automated partition generation for massive audit log scaling.

---
*Built as a showcase for Advanced Agentic Coding and System Design.*
