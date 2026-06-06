#!/bin/bash
# Deployment Verification Script

echo "Verifying Distributed Feature Flag Platform Deployment..."

# 1. Check API Service
echo "Checking API..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/live)
if [ "$API_STATUS" -eq 200 ]; then
    echo "✅ API is reachable"
else
    echo "❌ API is NOT reachable (HTTP $API_STATUS)"
    exit 1
fi

echo "Checking API Readiness..."
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ready)
if [ "$READY_STATUS" -eq 200 ]; then
    echo "✅ API is ready (Dependencies connected)"
else
    echo "❌ API dependencies are NOT ready (HTTP $READY_STATUS)"
    exit 1
fi

# 2. Check Prometheus
echo "Checking Prometheus..."
PROM_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/ready)
if [ "$PROM_STATUS" -eq 200 ]; then
    echo "✅ Prometheus is reachable"
else
    echo "❌ Prometheus is NOT reachable"
    exit 1
fi

# 3. Check Grafana
echo "Checking Grafana..."
GRAFANA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health)
if [ "$GRAFANA_STATUS" -eq 200 ]; then
    echo "✅ Grafana is reachable"
else
    echo "❌ Grafana is NOT reachable"
    exit 1
fi

# 4. Check Kafka UI
echo "Checking Kafka UI..."
KAFKA_UI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/actuator/health)
if [ "$KAFKA_UI_STATUS" -eq 200 ]; then
    echo "✅ Kafka UI is reachable"
else
    echo "❌ Kafka UI is NOT reachable"
    exit 1
fi

echo ""
echo "🎉 All services verified successfully!"
exit 0
