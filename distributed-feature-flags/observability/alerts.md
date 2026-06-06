# Prometheus Alerting Rules Design

This document details the critical alert rules to monitor the Feature Flag Platform.

## 1. Redis Cache Degradation
**Alert Name:** `RedisHitRateLow`
**Description:** Fires when the Redis cache hit rate falls below 80% over 10 minutes.
**PromQL:**
```yaml
- alert: RedisHitRateLow
  expr: |
    sum(rate(redis_cache_hits_total[5m])) / 
    (sum(rate(redis_cache_hits_total[5m])) + sum(rate(redis_cache_misses_total[5m]))) < 0.80
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Redis Cache Hit Rate dropped below 80%"
    description: "Hit rate is {{ $value }}. This indicates potential cache stampedes or massive invalidations."
```

## 2. Feature Flag Evaluation Errors
**Alert Name:** `FeatureFlagEvaluationErrorsHigh`
**Description:** Fires when feature flag evaluation failures spike.
**PromQL:**
```yaml
- alert: FeatureFlagEvaluationErrorsHigh
  expr: rate(feature_flag_evaluation_failures_total[5m]) > 1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "High Feature Flag Evaluation Errors"
    description: "Evaluator logic or database fallback is throwing exceptions for flag: {{ $labels.flag_key }}"
```

## 3. Outbox Publisher Lag
**Alert Name:** `OutboxPendingEventsGrowing`
**Description:** Fires when the pending outbox events constantly grow, indicating the publisher is down or Kafka is unreachable.
**PromQL:**
```yaml
- alert: OutboxPendingEventsGrowing
  expr: outbox_events_pending > 1000
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Outbox Queue Backlog"
    description: "There are {{ $value }} pending events waiting to be published to Kafka."
```

## 4. Evaluation Latency Threshold
**Alert Name:** `EvaluationLatencyHigh`
**Description:** Fires when the 99th percentile of feature flag evaluation latency exceeds 100ms.
**PromQL:**
```yaml
- alert: EvaluationLatencyHigh
  expr: histogram_quantile(0.99, sum by (le) (rate(evaluation_duration_seconds_bucket[5m]))) > 0.100
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Evaluation Latency High"
    description: "p99 Evaluation Latency is over 100ms. This usually indicates heavy database fallback."
```

## 5. SDK Refresh Failures
**Alert Name:** `SdkRefreshFailureRateHigh`
**Description:** Fires if more than 10% of background SDK refreshes fail.
**PromQL:**
```yaml
- alert: SdkRefreshFailureRateHigh
  expr: |
    sum(rate(sdk_snapshot_refresh_failures_total[5m])) / 
    sum(rate(sdk_snapshot_refresh_total[5m])) > 0.10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High SDK Refresh Failures"
    description: "Over 10% of background snapshot polling is failing. Check API availability and authentication."
```

## 6. HTTP API 5xx Errors
**Alert Name:** `HighApi5xxErrorRate`
**Description:** API 5xx error rate exceeds 5% of total requests.
**PromQL:**
```yaml
- alert: HighApi5xxErrorRate
  expr: |
    sum(rate(http_errors_total[5m])) / 
    sum(rate(http_requests_total[5m])) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "API 5xx Errors High"
    description: "Greater than 5% of all HTTP requests are failing with 5xx errors."
```
