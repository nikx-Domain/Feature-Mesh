import time

from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
)
from app.domain.evaluation.hashing import get_rollout_bucket
from app.domain.evaluation.models import (
    EvaluationContext,
    EvaluationDecision,
    EvaluationReason,
)
from app.domain.evaluation.operators import evaluate_operator


def evaluate_feature_flag(
    flag: FeatureFlagEntity,
    environment: FeatureFlagEnvironmentEntity,
    variations: list[FlagVariationEntity],
    context: EvaluationContext,
) -> EvaluationDecision:
    """
    Evaluates a feature flag state against a given context to determine the served variation.
    
    Returns an EvaluationDecision indicating the assigned variation and the reason.
    """
    start_time = time.perf_counter()
    decision = _evaluate_internal(flag, environment, variations, context)
    duration_ms = (time.perf_counter() - start_time) * 1000
    decision.metadata["duration_ms"] = round(duration_ms, 3)
    return decision


def _evaluate_internal(
    flag: FeatureFlagEntity,
    environment: FeatureFlagEnvironmentEntity,
    variations: list[FlagVariationEntity],
    context: EvaluationContext,
) -> EvaluationDecision:
    variation_map = {v.id: v for v in variations}

    # 1. Check if the flag environment is disabled
    if not environment.is_enabled:
        var_id = environment.off_variation_id
        variation = variation_map.get(var_id) if var_id else None
        return EvaluationDecision(
            feature_flag_key=flag.key,
            is_enabled=False,
            variation_id=var_id,
            variation_value=variation.value if variation else None,
            reason=EvaluationReason.DISABLED,
        )

    # 2. Evaluate Targeting Rules
    # Rules should be evaluated in order of their priority (ascending)
    sorted_rules = sorted(environment.targeting_rules, key=lambda r: r.priority)
    for rule in sorted_rules:
        context_value = context.attributes.get(rule.attribute)
        if evaluate_operator(context_value, rule.operator, rule.value):
            var_id = rule.serve_variation_id
            variation = variation_map.get(var_id)
            return EvaluationDecision(
                feature_flag_key=flag.key,
                is_enabled=True,
                variation_id=var_id,
                variation_value=variation.value if variation else None,
                reason=EvaluationReason.TARGETING_MATCH,
            )

    # 3. Evaluate Rollout Rules
    if environment.rollout_rules:
        bucket = get_rollout_bucket(flag.key, context.key)
        cumulative = 0
        sorted_rollout = sorted(environment.rollout_rules, key=lambda r: str(r.id))
        for rollout_rule in sorted_rollout:
            # `rollout_rule.percentage` is 0-100.
            # Bucket scale is 0-99999 (multiply by 1000)
            threshold = cumulative + (rollout_rule.percentage * 1000)
            if bucket < threshold:
                var_id = rollout_rule.serve_variation_id
                variation = variation_map.get(var_id)
                return EvaluationDecision(
                    feature_flag_key=flag.key,
                    is_enabled=True,
                    variation_id=var_id,
                    variation_value=variation.value if variation else None,
                    reason=EvaluationReason.ROLLOUT,
                )
            cumulative = threshold

    # 4. Fallback to Default Serve Variation
    var_id = environment.default_serve_variation_id
    variation = variation_map.get(var_id) if var_id else None
    return EvaluationDecision(
        feature_flag_key=flag.key,
        is_enabled=True,
        variation_id=var_id,
        variation_value=variation.value if variation else None,
        reason=EvaluationReason.DEFAULT,
    )
