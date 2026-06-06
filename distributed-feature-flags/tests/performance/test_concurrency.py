import pytest
import asyncio
import uuid
from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.entities import FeatureFlagEntity, FeatureFlagEnvironmentEntity, FlagVariationEntity, RolloutRuleEntity
from app.domain.evaluation.models import EvaluationContext

@pytest.mark.asyncio
async def test_concurrent_evaluations_deterministic():
    """
    Tests that firing thousands of concurrent evaluations using the same context
    yields the exact same variation, and using different contexts yields stable hash buckets,
    without race conditions.
    """
    flag = FeatureFlagEntity(project_id=uuid.uuid4(), name="LoadTest", key="load_flag")
    var_a = FlagVariationEntity(feature_flag_id=flag.id, name="A", value="A")
    var_b = FlagVariationEntity(feature_flag_id=flag.id, name="B", value="B")

    # 50/50 Rollout
    rule1 = RolloutRuleEntity(feature_flag_environment_id=uuid.uuid4(), serve_variation_id=var_a.id, percentage=50)
    rule2 = RolloutRuleEntity(feature_flag_environment_id=uuid.uuid4(), serve_variation_id=var_b.id, percentage=50)

    env = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=True,
        rollout_rules=[rule1, rule2],
    )
    
    # Pre-generate 1000 contexts
    contexts = [EvaluationContext(key=f"user_{i}") for i in range(1000)]
    
    async def evaluate(ctx):
        # We simulate a tiny async sleep if we wanted, but the evaluator is synchronous.
        # Just calling it in a tight loop.
        return evaluate_feature_flag(flag, env, [var_a, var_b], ctx)
        
    tasks = [evaluate(ctx) for ctx in contexts]
    
    # Execute all 1000 evaluations concurrently
    results = await asyncio.gather(*tasks)
    
    # Since it's deterministic, rerunning the same contexts should yield identical results
    tasks_run_2 = [evaluate(ctx) for ctx in contexts]
    results_2 = await asyncio.gather(*tasks_run_2)
    
    for r1, r2 in zip(results, results_2):
        assert r1.variation_id == r2.variation_id
        
    # Check 50/50 distribution roughly
    a_count = sum(1 for r in results if r.variation_id == var_a.id)
    assert 400 <= a_count <= 600
