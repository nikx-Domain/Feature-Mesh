import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.main import app
from app.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    REDIS_CACHE_HITS_TOTAL,
    FEATURE_FLAG_EVALUATIONS_TOTAL,
)

client = TestClient(app)

def test_metrics_endpoint_exposed():
    """Verify that the /metrics endpoint is exposed and returns Prometheus formatting."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "redis_cache_hits_total" in response.text


def test_http_request_metrics_recorded():
    """Verify that HTTP requests increment the HTTP_REQUESTS_TOTAL counter."""
    before = REGISTRY.get_sample_value("http_requests_total_total", labels={"method": "GET", "endpoint": "/health", "status_code": "200"}) or 0
    
    # Hit the health endpoint
    client.get("/health")
    
    after = REGISTRY.get_sample_value("http_requests_total_total", labels={"method": "GET", "endpoint": "/health", "status_code": "200"}) or 0
    assert after == before + 1


def test_metric_cardinality_rules():
    """Ensure no forbidden labels exist on the core metrics."""
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            labels = sample.labels
            assert "user_id" not in labels, "High cardinality label 'user_id' detected"
            assert "email" not in labels, "High cardinality label 'email' detected"
            assert "session_id" not in labels, "High cardinality label 'session_id' detected"
            assert "request_id" not in labels, "High cardinality label 'request_id' detected"


def test_custom_metric_increment():
    """Test manual increment of cache hits."""
    before = REGISTRY.get_sample_value("redis_cache_hits_total_total") or 0
    REDIS_CACHE_HITS_TOTAL.inc()
    after = REGISTRY.get_sample_value("redis_cache_hits_total_total") or 0
    assert after == before + 1


def test_feature_flag_evaluations_total():
    before = REGISTRY.get_sample_value("feature_flag_evaluations_total_total", labels={"flag_key": "test_flag", "reason": "DEFAULT"}) or 0
    FEATURE_FLAG_EVALUATIONS_TOTAL.labels(flag_key="test_flag", reason="DEFAULT").inc()
    after = REGISTRY.get_sample_value("feature_flag_evaluations_total_total", labels={"flag_key": "test_flag", "reason": "DEFAULT"}) or 0
    assert after == before + 1
