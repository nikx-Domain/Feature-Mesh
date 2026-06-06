# Shutdown Procedures

## Graceful Shutdown
To stop the platform while preserving data:
```bash
docker compose down
```
This sends `SIGTERM` to all containers. The API will cleanly close database connections, stop background tasks, and disconnect from Kafka/Redis gracefully.

## Complete Wipe (Including Data)
If you need to completely reset the environment and DESTROY ALL DATA:
```bash
docker compose down -v
```
This removes all containers, networks, and named volumes (deleting PostgreSQL data, Redis caches, Kafka logs, and Prometheus metrics).
