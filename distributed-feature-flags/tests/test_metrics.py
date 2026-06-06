import pytest
from app.observability.metrics import registry
from app.observability.evaluation_metrics import feature_flag_evaluations_total
from app.observability.redis_metrics import redis_cache_hits_total

def test_evaluation_metric_increments():
    before = registry.get_sample_value("feature_flag_evaluations_total_total", labels={"flag_key": "test_flag", "reason": "DEFAULT"}) or 0
    feature_flag_evaluations_total.labels(flag_key="test_flag", reason="DEFAULT").inc()
    after = registry.get_sample_value("feature_flag_evaluations_total_total", labels={"flag_key": "test_flag", "reason": "DEFAULT"}) or 0
    assert after == before + 1

def test_cache_metric_increments():
    before = registry.get_sample_value("redis_cache_hits_total_total") or 0
    redis_cache_hits_total.inc()
    after = registry.get_sample_value("redis_cache_hits_total_total") or 0
    assert after == before + 1

def test_metric_cardinality_rules():
    """Ensure no forbidden labels exist on the core metrics."""
    for metric in registry.collect():
        for sample in metric.samples:
            labels = sample.labels
            assert "user_id" not in labels, "High cardinality label 'user_id' detected"
            assert "email" not in labels, "High cardinality label 'email' detected"
            assert "session_id" not in labels, "High cardinality label 'session_id' detected"
            assert "request_id" not in labels, "High cardinality label 'request_id' detected"
