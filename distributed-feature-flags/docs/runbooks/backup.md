# Backup & Recovery Strategy

## PostgreSQL Backups
PostgreSQL is the source of truth for the platform.
To manually trigger a backup of the running database:
```bash
docker compose exec -T postgres pg_dump -U postgres feature_flags > backup_$(date +%F).sql
```
To restore:
```bash
cat backup_YYYY-MM-DD.sql | docker compose exec -T postgres psql -U postgres feature_flags
```

## Redis Backups
Redis operates primarily as a read-through cache, meaning data loss is generally acceptable and the cache will self-heal. However, it is configured with RDB snapshots by default to preserve state across restarts.
Snapshots are stored in the Docker volume `redis_data`.

## Grafana Configs
User-created dashboards should be exported as JSON and committed to the repository in `observability/grafana/dashboards/` to benefit from automatic provisioning on startup.

## Prometheus Data
Prometheus data is stored in the Docker volume `prometheus_data`. If long-term retention is required, configure remote-write to a durable backend like Thanos or Cortex, as local Prometheus storage is not designed for permanent archiving.
