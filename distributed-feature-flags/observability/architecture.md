# Observability Architecture

This document describes the observability architecture for the Distributed Feature Flag Platform. The goal of this architecture is to provide high visibility into the platform's performance, health, and operational correctness without tightly coupling observability logic to business domains.

## High-Level Architecture Flow

```
+-------------------+        +------------------------+        +-----------------+
|   Application     |        |   Prometheus Server    |        |    Grafana      |
| (FastAPI Backend) | -----> | (Scrapes /metrics)     | -----> | (Visualizations |
|                   |        |                        |        |   & Alerting)   |
+-------------------+        +------------------------+        +-----------------+
        |
        v
+-------------------+
|  Structured Logs  |
| (JSON / structlog)|
+-------------------+
```

1. **Application Layer**: The FastAPI application uses `prometheus_client` to track metrics in memory.
2. **Scraping**: A Prometheus server periodically scrapes the exposed `GET /metrics` endpoint.
3. **Visualization & Alerting**: Grafana connects to Prometheus as a data source to render dashboards and evaluate alert rules.

## Metrics Flow & Decoupling

To enforce the separation of concerns, no `prometheus_client` code exists in the core domain (e.g., `app/domain/evaluation/evaluator.py`).

Instead, the architecture utilizes the **Wrapper Pattern** and **Middleware**:
- **HTTP Metrics**: Intercepted at the edge via `ObservabilityMiddleware`.
- **Evaluation Metrics**: Recorded in the Use Case layer (`evaluate_feature_flag.py`), wrapping the pure domain evaluator.
- **Infrastructure Metrics**: Recorded directly in the implementations of interfaces (`redis_cache_service.py`, `outbox_publisher.py`).

All metric singletons are centrally defined within the `app/observability/` package to prevent duplication.

## Logging Flow

We use `structlog` to provide structured JSON logging.
- **Traceability**: Every request is assigned a `request_id` (and optionally a `correlation_id` from headers).
- **Context Injection**: `structlog.contextvars` is used to bind these IDs to a thread-local context, ensuring every log emitted during the request lifecycle automatically includes the IDs.
- **Format**: Logs are rendered as plain text in `development` environments and strictly as JSON in production systems to enable easy parsing by log aggregators (e.g., ELK, Datadog, Loki).

## Alert Flow

Alerts are defined via PromQL (see `alerts.md`). Prometheus evaluates these rules periodically. When a rule condition is met (e.g., `EvaluationLatencyHigh`), Prometheus transitions the alert to a firing state and sends it to an Alertmanager, which routes it to incident response tools (e.g., PagerDuty, Slack).

## Cardinality Review

A core design principle of our metrics strategy is protecting the Prometheus server from high-cardinality explosions.

**High-cardinality metrics are dangerous because:**
Prometheus creates a new time series in its time-series database (TSDB) for every unique combination of labels. If we include a label with unbounded unique values (like millions of user IDs), Prometheus will run out of memory, crash, or become unresponsive when queried.

**Forbidden Labels:**
- `user_id`
- `email`
- `session_id`
- `request_id`

**Allowed Labels (Bounded Dimensions):**
- `endpoint` (must be parameterized, e.g., `/projects/{id}` not `/projects/123`)
- `method` (GET, POST)
- `status_code` (200, 404, 500)
- `flag_key` (typically hundreds or thousands, which is acceptable)
- `reason` (TARGETING_MATCH, DEFAULT, etc.)
- `topic` (Kafka topics)
