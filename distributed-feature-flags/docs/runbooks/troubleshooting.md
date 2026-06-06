# Troubleshooting Guide

## Common Failure Scenarios

### API Container Exits Immediately / Restart Loop
**Symptoms**: `docker compose ps` shows `feature_flag_api` continually restarting.
**Diagnosis**: The API is likely failing its startup sequence.
**Resolution**:
1. Check logs: `docker compose logs api`
2. Ensure `.env` is correctly populated.
3. Ensure PostgreSQL, Redis, and Kafka are healthy. Check their logs if they are not.

### Kafka / Zookeeper Out of Memory
**Symptoms**: Kafka container dies with exit code 137 (OOM Killed).
**Resolution**:
Kafka requires significant RAM. If running Docker Desktop, ensure the VM has at least 4GB of memory allocated.

### Missing Data in Grafana
**Symptoms**: Dashboard is empty or shows "No Data".
**Resolution**:
1. Ensure the API is receiving traffic (metrics are generated on HTTP requests).
2. Check Prometheus targets: `http://localhost:9090/targets` to verify Prometheus is successfully scraping the API container.

### Stale Feature Flags (Cache Not Invalidating)
**Symptoms**: SDKs receive outdated flags despite DB updates.
**Resolution**:
1. Check Kafka UI (`http://localhost:8080`) to ensure the `feature-flag-events` topic is receiving events.
2. Check API logs for consumer errors processing invalidation events.
3. As a fallback, clear Redis: `docker compose exec redis redis-cli flushall`
