# Startup Procedures

## Standard Startup
To start the entire Distributed Feature Flag platform:

```bash
docker compose up -d
```
Docker Compose will automatically resolve dependencies. The API container (`feature_flag_api`) will wait until PostgreSQL, Redis, and Kafka pass their health checks before attempting to bind to port 8000.

## Verifying Startup
Use the provided verification script to ensure all components are healthy:
```bash
./scripts/verify_deployment.sh
```
A successful startup outputs:
```
✅ API is reachable
✅ API is ready (Dependencies connected)
✅ Prometheus is reachable
✅ Grafana is reachable
✅ Kafka UI is reachable
🎉 All services verified successfully!
```

## Cold Boot Caveats
On the very first boot, downloading images (`postgres`, `redis`, `kafka`, `python`, `grafana`) will take several minutes. Ensure sufficient disk space and network bandwidth.
