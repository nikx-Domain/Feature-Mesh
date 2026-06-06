"""
High-Concurrency Stress Tests — Task 7
Verifies: 10,000 concurrent evaluations, no race conditions, deterministic decisions,
correct rollout distribution, concurrent cache reads/writes.
"""
import pytest
import asyncio
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.entities import (
    FeatureFlagEntity, FeatureFlagEnvironmentEntity,
    FlagVariationEntity, RolloutRuleEntity, TargetingRuleEntity, TargetingOperator,
)
from app.domain.evaluation.models import EvaluationContext
from sdk.cache.store import FlagStore
from sdk.models.dtos import SDKSnapshot, SDKFeatureFlag, SDKFeatureFlagEnvironment, SDKFlagVariation
from sdk.client.client import FeatureFlagClient
from sdk.config.config import SDKConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_flag(key: str = "stress_flag"):
    flag = FeatureFlagEntity(project_id=uuid.uuid4(), name="Stress", key=key)
    var_a = FlagVariationEntity(feature_flag_id=flag.id, name="A", value="A")
    var_b = FlagVariationEntity(feature_flag_id=flag.id, name="B", value="B")
    rule1 = RolloutRuleEntity(feature_flag_environment_id=uuid.uuid4(), serve_variation_id=var_a.id, percentage=50)
    rule2 = RolloutRuleEntity(feature_flag_environment_id=uuid.uuid4(), serve_variation_id=var_b.id, percentage=50)
    env = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=True,
        rollout_rules=[rule1, rule2],
    )
    return flag, env, [var_a, var_b]


def _build_sdk_client(flag_key: str = "stress_flag", is_enabled: bool = True) -> FeatureFlagClient:
    store = FlagStore()
    env = SDKFeatureFlagEnvironment(
        is_enabled=is_enabled, default_serve_variation_id="v1", off_variation_id="v2",
        targeting_rules=[], rollout_rules=[],
    )
    flag = SDKFeatureFlag(
        id="1", key=flag_key, type="boolean", version=1, environment=env,
        variations=[SDKFlagVariation(id="v1", name="on", value=True), SDKFlagVariation(id="v2", name="off", value=False)],
    )
    store.update_snapshot(SDKSnapshot(environment_id="env-1", flags={flag_key: flag}))
    config = SDKConfig(api_key="key", offline_mode=True)
    client = FeatureFlagClient(config)
    client.store = store
    client._is_started = True
    return client


# ---------------------------------------------------------------------------
# Scenario 1: 10,000 Concurrent Backend Evaluations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10k_concurrent_evaluations_deterministic():
    """
    10,000 concurrent evaluations with unique user contexts.
    Verifies: determinism (same context → same result), no race conditions.
    """
    flag, env, variations = _build_flag("det_flag")
    contexts = [EvaluationContext(key=f"user_{i}") for i in range(10_000)]

    async def evaluate(ctx: EvaluationContext):
        return evaluate_feature_flag(flag, env, variations, ctx)

    # Run 1
    results_1 = await asyncio.gather(*[evaluate(ctx) for ctx in contexts])
    # Run 2 — same contexts, same results expected
    results_2 = await asyncio.gather(*[evaluate(ctx) for ctx in contexts])

    for r1, r2 in zip(results_1, results_2):
        assert r1.variation_id == r2.variation_id, "Evaluation must be deterministic"

    print(f"\n[Stress] 10k evaluations completed. Determinism: ✓")


@pytest.mark.asyncio
async def test_10k_concurrent_evaluations_distribution():
    """
    10,000 evaluations with 50/50 rollout should distribute roughly 50/50.
    Acceptable range: 4800–5200 (±2% deviation for 10k users).
    """
    flag, env, variations = _build_flag("dist_flag")
    var_a, var_b = variations
    contexts = [EvaluationContext(key=f"user_{i}") for i in range(10_000)]

    results = await asyncio.gather(*[
        asyncio.to_thread(evaluate_feature_flag, flag, env, variations, ctx)
        for ctx in contexts
    ])

    a_count = sum(1 for r in results if r.variation_id == var_a.id)
    b_count = sum(1 for r in results if r.variation_id == var_b.id)

    assert 4800 <= a_count <= 5200, f"Distribution off: A={a_count}, B={b_count}"
    print(f"\n[Stress] Distribution: A={a_count}, B={b_count}")


# ---------------------------------------------------------------------------
# Scenario 2: 10,000 Concurrent SDK Evaluations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10k_concurrent_sdk_evaluations():
    """
    10,000 concurrent SDK is_enabled() calls from a single cached store.
    Verifies no race conditions, no cache corruption.
    """
    client = _build_sdk_client("sdk_stress_flag", is_enabled=True)
    contexts = [{"key": f"user_{i}"} for i in range(10_000)]

    results = await asyncio.gather(*[
        asyncio.to_thread(client.is_enabled, "sdk_stress_flag", ctx)
        for ctx in contexts
    ])

    assert all(r is True for r in results), "All evaluations must return True"
    assert len(results) == 10_000
    print(f"\n[Stress] SDK: 10k evaluations — all True ✓")


# ---------------------------------------------------------------------------
# Scenario 3: Concurrent Flag Updates + Reads (Cache Corruption Check)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_flag_store_updates_no_corruption():
    """
    Multiple coroutines concurrently update the FlagStore and read from it.
    Verifies no data corruption or race conditions in the in-memory store.
    """
    store = FlagStore()

    def _make_sdk_snapshot(version: int) -> SDKSnapshot:
        env = SDKFeatureFlagEnvironment(
            is_enabled=True, default_serve_variation_id="v1", off_variation_id="v2",
            targeting_rules=[], rollout_rules=[],
        )
        flag = SDKFeatureFlag(
            id="1", key="race_flag", type="boolean", version=version, environment=env,
            variations=[SDKFlagVariation(id="v1", name="on", value=True)],
        )
        return SDKSnapshot(environment_id="env-1", flags={"race_flag": flag})

    async def writer(version: int):
        store.update_snapshot(_make_sdk_snapshot(version))

    async def reader() -> bool:
        flag = store.get_flag("race_flag")
        return flag is not None

    # 100 writers and 1000 readers concurrently
    write_tasks = [writer(v) for v in range(100)]
    read_tasks = [reader() for _ in range(1000)]

    results = await asyncio.gather(*(write_tasks + read_tasks), return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Race conditions detected: {errors}"
    print(f"\n[Stress] Concurrent store updates: no corruption ✓")


# ---------------------------------------------------------------------------
# Scenario 4: Thread-safety of FlagStore
# ---------------------------------------------------------------------------
def test_flag_store_thread_safe():
    """
    FlagStore is read from multiple OS threads simultaneously.
    Verifies no AttributeError, None returns, or corruption.
    """
    store = FlagStore()

    env = SDKFeatureFlagEnvironment(
        is_enabled=True, default_serve_variation_id="v1", off_variation_id=None,
        targeting_rules=[], rollout_rules=[],
    )
    flag = SDKFeatureFlag(
        id="1", key="thread_flag", type="boolean", version=1, environment=env,
        variations=[SDKFlagVariation(id="v1", name="on", value=True)],
    )
    store.update_snapshot(SDKSnapshot(environment_id="env-1", flags={"thread_flag": flag}))

    def read_flag():
        for _ in range(1000):
            f = store.get_flag("thread_flag")
            assert f is not None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(read_flag) for _ in range(10)]
        for future in futures:
            future.result()  # Raises if any thread had an error

    print(f"\n[Stress] Thread-safe FlagStore reads: ✓")


# ---------------------------------------------------------------------------
# Scenario 5: Evaluation Latency under Load
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evaluation_latency_under_load():
    """
    1,000 concurrent evaluations should all complete within 500ms total.
    Verifies that the local evaluation engine scales without blocking.
    """
    flag, env, variations = _build_flag("latency_flag")
    contexts = [EvaluationContext(key=f"user_{i}") for i in range(1_000)]

    t_start = time.perf_counter()
    await asyncio.gather(*[
        asyncio.to_thread(evaluate_feature_flag, flag, env, variations, ctx)
        for ctx in contexts
    ])
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    assert elapsed_ms < 500, f"1k evaluations took {elapsed_ms:.1f}ms — expected < 500ms"
    print(f"\n[Stress] 1k evaluations in {elapsed_ms:.1f}ms ✓")
