import uuid
from typing import Any

from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
    RolloutRuleEntity,
    TargetingRuleEntity,
    FlagType,
    TargetingOperator
)
from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.evaluation.models import EvaluationContext, EvaluationDecision
from sdk.models.dtos import SDKFeatureFlagDTO


class EvaluationEngineAdapter:
    """
    Adapts SDK DTOs into backend Domain Entities to execute local evaluation
    using the exact same logic as the backend without reimplementing it.
    """

    @staticmethod
    def evaluate(flag_dto: SDKFeatureFlagDTO, context_dict: dict[str, Any]) -> EvaluationDecision:
        # Build EvaluationContext
        # A simple hashing key generation for rollout (usually context['key'] or similar)
        # If no key is provided, we can fallback to a random string or a hardcoded one,
        # but the backend hashing relies on a context key.
        context_key = str(context_dict.get("key", uuid.uuid4()))
        context = EvaluationContext(key=context_key, attributes=context_dict)

        # Map DTOs to Entities
        flag_entity = FeatureFlagEntity(
            id=uuid.UUID(flag_dto.id),
            project_id=uuid.uuid4(), # Not used in evaluation logic
            name=flag_dto.key,       # Not used in evaluation logic
            key=flag_dto.key,
            type=FlagType(flag_dto.type),
            version=flag_dto.version,
        )

        variations = [
            FlagVariationEntity(
                id=uuid.UUID(v.id),
                feature_flag_id=flag_entity.id,
                name=v.name,
                value=v.value
            )
            for v in flag_dto.variations
        ]

        env_dto = flag_dto.environment
        
        targeting_rules = [
            TargetingRuleEntity(
                id=uuid.UUID(r.id),
                feature_flag_environment_id=uuid.uuid4(),
                attribute=r.attribute,
                operator=TargetingOperator(r.operator),
                value=r.value,
                serve_variation_id=uuid.UUID(r.serve_variation_id),
                priority=r.priority
            )
            for r in env_dto.targeting_rules
        ]
        
        rollout_rules = [
            RolloutRuleEntity(
                id=uuid.UUID(r.id),
                feature_flag_environment_id=uuid.uuid4(),
                serve_variation_id=uuid.UUID(r.serve_variation_id),
                percentage=r.percentage
            )
            for r in env_dto.rollout_rules
        ]

        env_entity = FeatureFlagEnvironmentEntity(
            id=uuid.uuid4(),
            feature_flag_id=flag_entity.id,
            environment_id=uuid.uuid4(),
            is_enabled=env_dto.is_enabled,
            default_serve_variation_id=uuid.UUID(env_dto.default_serve_variation_id) if env_dto.default_serve_variation_id else None,
            off_variation_id=uuid.UUID(env_dto.off_variation_id) if env_dto.off_variation_id else None,
            targeting_rules=targeting_rules,
            rollout_rules=rollout_rules
        )

        # Call the existing evaluation engine logic
        decision = evaluate_feature_flag(
            flag=flag_entity,
            environment=env_entity,
            variations=variations,
            context=context
        )
        
        return decision
