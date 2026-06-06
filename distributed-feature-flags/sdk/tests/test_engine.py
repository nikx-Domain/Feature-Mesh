import pytest
from sdk.evaluation.engine import LocalEvaluationEngine
from sdk.models.dtos import SDKFeatureFlag, SDKFeatureFlagEnvironment, SDKFlagVariation, SDKTargetingRule, SDKRolloutRule

def test_evaluate_operator_equals():
    assert LocalEvaluationEngine.evaluate_operator("a", "equals", "a") is True
    assert LocalEvaluationEngine.evaluate_operator("a", "equals", "b") is False

def test_evaluate_operator_not_equals():
    assert LocalEvaluationEngine.evaluate_operator("a", "not_equals", "b") is True
    assert LocalEvaluationEngine.evaluate_operator("a", "not_equals", "a") is False

def test_evaluate_operator_in():
    assert LocalEvaluationEngine.evaluate_operator("a", "in", ["a", "b"]) is True
    assert LocalEvaluationEngine.evaluate_operator("c", "in", ["a", "b"]) is False

def test_evaluate_operator_not_in():
    assert LocalEvaluationEngine.evaluate_operator("c", "not_in", ["a", "b"]) is True
    assert LocalEvaluationEngine.evaluate_operator("a", "not_in", ["a", "b"]) is False

def test_evaluate_operator_contains():
    assert LocalEvaluationEngine.evaluate_operator("abc", "contains", "b") is True
    assert LocalEvaluationEngine.evaluate_operator("abc", "contains", "d") is False

def test_evaluate_operator_not_contains():
    assert LocalEvaluationEngine.evaluate_operator("abc", "not_contains", "d") is True
    assert LocalEvaluationEngine.evaluate_operator("abc", "not_contains", "b") is False

def test_evaluate_operator_matches_regex():
    assert LocalEvaluationEngine.evaluate_operator("abc", "matches_regex", "^a.*") is True
    assert LocalEvaluationEngine.evaluate_operator("abc", "matches_regex", "^b.*") is False
    assert LocalEvaluationEngine.evaluate_operator("abc", "matches_regex", "[") is False

def test_evaluate_operator_greater_than():
    assert LocalEvaluationEngine.evaluate_operator(5, "greater_than", 3) is True
    assert LocalEvaluationEngine.evaluate_operator(3, "greater_than", 5) is False
    assert LocalEvaluationEngine.evaluate_operator("b", "greater_than", "a") is True

def test_evaluate_operator_less_than():
    assert LocalEvaluationEngine.evaluate_operator(3, "less_than", 5) is True
    assert LocalEvaluationEngine.evaluate_operator(5, "less_than", 3) is False
    assert LocalEvaluationEngine.evaluate_operator("a", "less_than", "b") is True

def test_evaluate_operator_null_context():
    assert LocalEvaluationEngine.evaluate_operator(None, "equals", "a") is False
    assert LocalEvaluationEngine.evaluate_operator(None, "not_equals", "a") is True

def test_evaluate_flag_disabled():
    env = SDKFeatureFlagEnvironment(is_enabled=False, default_serve_variation_id="v1", off_variation_id="v2", targeting_rules=[], rollout_rules=[])
    var1 = SDKFlagVariation(id="v1", name="v1", value=True)
    var2 = SDKFlagVariation(id="v2", name="v2", value=False)
    flag = SDKFeatureFlag(id="1", key="test", type="boolean", version=1, environment=env, variations=[var1, var2])
    
    decision = LocalEvaluationEngine.evaluate(flag, {})
    assert decision.is_enabled is False
    assert decision.variation_id == "v2"
    assert decision.variation_value is False
    assert decision.reason == "DISABLED"

def test_evaluate_flag_targeting():
    rule = SDKTargetingRule(id="1", attribute="email", operator="equals", value="test@test.com", serve_variation_id="v1", priority=1)
    env = SDKFeatureFlagEnvironment(is_enabled=True, default_serve_variation_id="v2", off_variation_id="v2", targeting_rules=[rule], rollout_rules=[])
    var1 = SDKFlagVariation(id="v1", name="v1", value=True)
    var2 = SDKFlagVariation(id="v2", name="v2", value=False)
    flag = SDKFeatureFlag(id="1", key="test", type="boolean", version=1, environment=env, variations=[var1, var2])
    
    decision = LocalEvaluationEngine.evaluate(flag, {"email": "test@test.com"})
    assert decision.is_enabled is True
    assert decision.variation_id == "v1"
    assert decision.reason == "TARGETING_MATCH"

def test_evaluate_flag_rollout():
    rule = SDKRolloutRule(id="1", percentage=100, serve_variation_id="v1")
    env = SDKFeatureFlagEnvironment(is_enabled=True, default_serve_variation_id="v2", off_variation_id="v2", targeting_rules=[], rollout_rules=[rule])
    var1 = SDKFlagVariation(id="v1", name="v1", value=True)
    var2 = SDKFlagVariation(id="v2", name="v2", value=False)
    flag = SDKFeatureFlag(id="1", key="test", type="boolean", version=1, environment=env, variations=[var1, var2])
    
    decision = LocalEvaluationEngine.evaluate(flag, {"key": "user1"})
    assert decision.is_enabled is True
    assert decision.variation_id == "v1"
    assert decision.reason == "ROLLOUT"
