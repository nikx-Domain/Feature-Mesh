# Grafana Dashboards Design

This document outlines the panels and PromQL queries for the 5 requested Grafana dashboards.

## Dashboard 1: Feature Flag Health
**Goal:** Track evaluations, matches, and failure rates per flag.

### Panels
1. **Total Evaluations (Stat)**
   - Query: `sum(rate(feature_flag_evaluations_total[5m]))`
2. **Evaluations by Flag (Time Series)**
   - Query: `sum by (flag_key) (rate(feature_flag_evaluations_total[5m]))`
3. **Evaluation Failures (Time Series)**
   - Query: `sum by (flag_key) (rate(feature_flag_evaluation_failures_total[5m]))`
4. **Targeting Matches vs Rollout (Bar Gauge)**
   - Targeting: `sum(rate(feature_flag_targeting_matches_total[5m]))`
   - Rollout: `sum(rate(feature_flag_rollout_matches_total[5m]))`
5. **Evaluation Latency p95 / p99 (Time Series)**
   - Query: `histogram_quantile(0.99, sum by (le) (rate(evaluation_duration_seconds_bucket[5m])))`

## Dashboard 2: Redis Performance
**Goal:** Monitor cache effectiveness and infrastructure health.

### Panels
1. **Cache Hit Ratio (Gauge)**
   - Query: `sum(rate(redis_cache_hits_total[5m])) / (sum(rate(redis_cache_hits_total[5m])) + sum(rate(redis_cache_misses_total[5m])))`
2. **Cache Miss & Rebuild Rate (Time Series)**
   - Query: `sum(rate(redis_cache_rebuilds_total[5m]))`
3. **Redis Operations Breakdown (Pie Chart)**
   - Query: `sum by (action) (rate(redis_cache_errors_total[5m]))` (To monitor where errors occur)
4. **Cache Reads (Time Series)**
   - Query: `rate(redis_cache_hits_total[5m]) + rate(redis_cache_misses_total[5m])`

## Dashboard 3: Kafka & Outbox
**Goal:** Track message broker throughput and outbox background job processing.

### Panels
1. **Events Published (Time Series)**
   - Query: `sum by (topic) (rate(kafka_events_published_total[5m]))`
2. **Consumer Processing Rate (Time Series)**
   - Query: `sum by (topic) (rate(kafka_consumer_processed_total[5m]))`
3. **Pending Outbox Events (Stat)**
   - Query: `max(outbox_events_pending)`
4. **Outbox Processed vs Failed (Time Series)**
   - Processed: `sum(rate(outbox_events_processed_total[5m]))`
   - Failed: `sum by (topic) (rate(kafka_events_failed_total[5m]))`

## Dashboard 4: API Performance
**Goal:** High-level view of HTTP traffic hitting the control plane.

### Panels
1. **Request Rate (Time Series)**
   - Query: `sum by (endpoint, method) (rate(http_requests_total[5m]))`
2. **HTTP 5xx Error Rate (Time Series)**
   - Query: `sum by (endpoint) (rate(http_errors_total[5m]))`
3. **API Latency p99 (Time Series)**
   - Query: `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))`

## Dashboard 5: SDK Health
**Goal:** Monitor the operational health of connected SDKs based on their self-reported metrics (or server side tracking of snapshot endpoint hits).

### Panels
1. **Snapshot Refresh Rate (Time Series)**
   - Query: `sum by (status) (rate(sdk_snapshot_refresh_total[5m]))`
2. **Cache Replacements (Time Series)**
   - Query: `sum(rate(sdk_cache_replacements_total[5m]))`
3. **Local Evaluations Rate (Time Series)**
   - Query: `sum by (flag_key) (rate(sdk_evaluations_total[5m]))`
4. **Refresh Failure Rate (Stat)**
   - Query: `sum(rate(sdk_snapshot_refresh_failures_total[5m])) / sum(rate(sdk_snapshot_refresh_total[5m]))`
