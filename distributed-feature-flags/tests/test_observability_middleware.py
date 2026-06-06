from fastapi.testclient import TestClient
from app.main import app
from app.observability.metrics import registry

client = TestClient(app)

def test_http_request_metrics_recorded():
    """Verify that HTTP requests increment the HTTP_REQUESTS_TOTAL counter."""
    before = registry.get_sample_value("http_requests_total", labels={"method": "GET", "endpoint": "/health", "status_code": "200"}) or 0
    
    # Hit the health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    
    after = registry.get_sample_value("http_requests_total", labels={"method": "GET", "endpoint": "/health", "status_code": "200"}) or 0
    assert after == before + 1

def test_http_metrics_excludes_metrics_endpoint():
    """Verify that hitting /metrics does not increment the requests counter."""
    before = registry.get_sample_value("http_requests_total", labels={"method": "GET", "endpoint": "/metrics", "status_code": "200"}) or 0
    
    client.get("/metrics")
    
    after = registry.get_sample_value("http_requests_total", labels={"method": "GET", "endpoint": "/metrics", "status_code": "200"}) or 0
    assert after == before # Should not increment
