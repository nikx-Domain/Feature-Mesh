from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_metrics_endpoint_exposed():
    """Verify that the /metrics endpoint is exposed and returns Prometheus formatting."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "redis_cache_hits_total" in response.text
