import uuid

from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
    RolloutRuleEntity,
    TargetingOperator,
    TargetingRuleEntity,
)
from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.evaluation.hashing import get_rollout_bucket
from app.domain.evaluation.models import EvaluationContext, EvaluationReason
from app.domain.evaluation.operators import evaluate_operator


def test_evaluate_operator():
    assert evaluate_operator("test", TargetingOperator.EQUALS, "test") is True
    assert evaluate_operator("test", TargetingOperator.EQUALS, "other") is False
    assert evaluate_operator("test", TargetingOperator.NOT_EQUALS, "other") is True
    assert evaluate_operator("test", TargetingOperator.IN, ["test", "other"]) is True
    assert evaluate_operator("other", TargetingOperator.NOT_IN, ["test"]) is True
    assert evaluate_operator("hello world", TargetingOperator.CONTAINS, "world") is True
    assert evaluate_operator("hello", TargetingOperator.MATCHES_REGEX, "^h.*o$") is True
    assert evaluate_operator(5, TargetingOperator.GREATER_THAN, 3) is True
    assert evaluate_operator("b", TargetingOperator.LESS_THAN, "c") is True
    assert evaluate_operator("10", TargetingOperator.GREATER_THAN, 3) is False  # Type mismatch
    assert evaluate_operator(None, TargetingOperator.EQUALS, "test") is False


def test_get_rollout_bucket():
    # Should be deterministic
    bucket1 = get_rollout_bucket("flag1", "user1")
    bucket2 = get_rollout_bucket("flag1", "user1")
    assert bucket1 == bucket2
    assert 0 <= bucket1 < 100000

    bucket3 = get_rollout_bucket("flag2", "user1")
    assert bucket1 != bucket3  # Different flags hash users differently


def test_evaluate_feature_flag_disabled():
    flag = FeatureFlagEntity(project_id=uuid.uuid4(), name="Test", key="test_flag")
    var_off = FlagVariationEntity(feature_flag_id=flag.id, name="Off", value=False)
    var_on = FlagVariationEntity(feature_flag_id=flag.id, name="On", value=True)
    env = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=False,
        off_variation_id=var_off.id,
        default_serve_variation_id=var_on.id,
    )

    context = EvaluationContext(key="user1")
    decision = evaluate_feature_flag(flag, env, [var_off, var_on], context)

    assert decision.is_enabled is False
    assert decision.reason == EvaluationReason.DISABLED
    assert decision.variation_id == var_off.id
    assert decision.variation_value is False


def test_evaluate_feature_flag_targeting():
    flag = FeatureFlagEntity(project_id=uuid.uuid4(), name="Test", key="test_flag")
    var_a = FlagVariationEntity(feature_flag_id=flag.id, name="A", value="A")
    var_b = FlagVariationEntity(feature_flag_id=flag.id, name="B", value="B")

    rule = TargetingRuleEntity(
        feature_flag_environment_id=uuid.uuid4(),
        attribute="country",
        operator=TargetingOperator.EQUALS,
        value="US",
        serve_variation_id=var_b.id,
        priority=0,
    )

    env = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=True,
        default_serve_variation_id=var_a.id,
        targeting_rules=[rule],
    )

    # Context matches US -> serves B
    context = EvaluationContext(key="user1", attributes={"country": "US"})
    decision = evaluate_feature_flag(flag, env, [var_a, var_b], context)
    assert decision.reason == EvaluationReason.TARGETING_MATCH
    assert decision.variation_id == var_b.id

    # Context does not match -> fallback to default (A)
    context2 = EvaluationContext(key="user2", attributes={"country": "CA"})
    decision2 = evaluate_feature_flag(flag, env, [var_a, var_b], context2)
    assert decision2.reason == EvaluationReason.DEFAULT
    assert decision2.variation_id == var_a.id


def test_evaluate_feature_flag_rollout():
    flag = FeatureFlagEntity(project_id=uuid.uuid4(), name="Test", key="test_flag")
    var_a = FlagVariationEntity(feature_flag_id=flag.id, name="A", value="A")
    var_b = FlagVariationEntity(feature_flag_id=flag.id, name="B", value="B")

    # 10% get B, 90% get A
    rule1 = RolloutRuleEntity(
        feature_flag_environment_id=uuid.uuid4(),
        serve_variation_id=var_b.id,
        percentage=10,
    )
    rule2 = RolloutRuleEntity(
        feature_flag_environment_id=uuid.uuid4(),
        serve_variation_id=var_a.id,
        percentage=90,
    )

    env = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=True,
        rollout_rules=[rule1, rule2],
    )

    b_count = 0
    total = 1000
    for i in range(total):
        context = EvaluationContext(key=f"user_{i}")
        decision = evaluate_feature_flag(flag, env, [var_a, var_b], context)
        assert decision.reason == EvaluationReason.ROLLOUT
        if decision.variation_id == var_b.id:
            b_count += 1

    # Should be around 10% (100).
    assert 70 <= b_count <= 130
