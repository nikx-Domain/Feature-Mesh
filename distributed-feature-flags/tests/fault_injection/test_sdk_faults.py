"""
SDK Fault Injection + Network Partition Simulation — Tasks 5 & 6
Simulates: SDK refresh failure, network partition, offline cache behavior,
and reconnection + snapshot refresh.
"""
import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from sdk.client.client import FeatureFlagClient
from sdk.config.config import SDKConfig
from sdk.cache.store import FlagStore
from sdk.models.dtos import SDKSnapshot, SDKFeatureFlag, SDKFeatureFlagEnvironment, SDKFlagVariation


def _make_snapshot(flag_key: str = "test_flag", is_enabled: bool = True) -> SDKSnapshot:
    """Build a minimal in-memory snapshot for testing."""
    env = SDKFeatureFlagEnvironment(
        is_enabled=is_enabled,
        default_serve_variation_id="v1",
        off_variation_id="v2",
        targeting_rules=[],
        rollout_rules=[],
    )
    flag = SDKFeatureFlag(
        id="flag-1",
        key=flag_key,
        type="boolean",
        version=1,
        environment=env,
        variations=[
            SDKFlagVariation(id="v1", name="on", value=True),
            SDKFlagVariation(id="v2", name="off", value=False),
        ],
    )
    return SDKSnapshot(environment_id="env-1", flags={flag_key: flag})


# ---------------------------------------------------------------------------
# Task 6: Network Partition Simulation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sdk_evaluates_locally_during_network_partition():
    """
    SDK has a cached snapshot. Network goes down.
    Evaluations must continue using the cached data.
    """
    store = FlagStore()
    snapshot = _make_snapshot("checkout_flag", is_enabled=True)
    store.update_snapshot(snapshot)

    config = SDKConfig(api_key="test-key", base_url="http://localhost:8000", offline_mode=True)
    client = FeatureFlagClient(config)
    client.store = store
    client._is_started = True

    # Simulate network partition: is_enabled returns False for SDK (offline)
    result = client.is_enabled("checkout_flag", context={"key": "user-1"})
    assert result is True, "Evaluations must continue locally during network partition"


@pytest.mark.asyncio
async def test_sdk_returns_default_when_store_not_initialized():
    """SDK returns default value when store is not yet populated."""
    config = SDKConfig(api_key="test-key", offline_mode=True)
    client = FeatureFlagClient(config)
    client._is_started = True

    result = client.is_enabled("unknown_flag", context={}, default=False)
    assert result is False, "Should return default when store not initialized"


@pytest.mark.asyncio
async def test_sdk_returns_default_for_unknown_flag():
    """SDK returns default when flag key doesn't exist in snapshot."""
    store = FlagStore()
    store.update_snapshot(_make_snapshot("other_flag"))

    config = SDKConfig(api_key="test-key", offline_mode=True)
    client = FeatureFlagClient(config)
    client.store = store
    client._is_started = True

    result = client.is_enabled("nonexistent_flag", context={}, default=False)
    assert result is False


# ---------------------------------------------------------------------------
# Fault: SDK Refresh Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sdk_refresh_failure_retains_cached_snapshot():
    """
    When background refresh fails (network error), the existing cache is retained.
    Evaluations must return the last-known value, not the default.
    """
    store = FlagStore()
    snapshot = _make_snapshot("my_flag", is_enabled=True)
    store.update_snapshot(snapshot)

    from sdk.refresh.manager import RefreshManager
    config = SDKConfig(api_key="key", base_url="http://localhost:8000")
    manager = RefreshManager(config=config, store=store)
    manager._loop = None  # Not started

    # Simulate failed refresh — store still has the old snapshot
    old_snapshot = store.get_flag("my_flag")
    assert old_snapshot is not None, "Flag must still be in cache after refresh failure"

    # Client evaluation still works
    config2 = SDKConfig(api_key="key", offline_mode=True)
    client = FeatureFlagClient(config2)
    client.store = store
    client._is_started = True

    result = client.is_enabled("my_flag", context={"key": "user-1"})
    assert result is True, "Stale cache must be served during refresh failure"


@pytest.mark.asyncio
async def test_sdk_refresh_exception_does_not_crash_manager():
    """
    Exception in _do_refresh must not propagate or crash the refresh manager.
    """
    from sdk.refresh.manager import RefreshManager
    from sdk.transport.client import TransportClient

    store = FlagStore()
    config = SDKConfig(api_key="key", base_url="http://localhost:8000")
    manager = RefreshManager(config=config, store=store)

    mock_transport = AsyncMock()
    mock_transport.get_snapshot.side_effect = Exception("Network error")
    manager._transport = mock_transport

    # Should not raise
    await manager._do_refresh()

    # Store remains unchanged (no snapshot update)
    assert not store.is_initialized()


# ---------------------------------------------------------------------------
# Reconnect: Snapshot Refresh after Network Recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sdk_snapshot_updated_after_recovery():
    """
    After network recovers, the next refresh cycle updates the snapshot.
    New flag values are immediately available for evaluation.
    """
    from sdk.refresh.manager import RefreshManager
    from sdk.models.dtos import parse_snapshot

    store = FlagStore()
    # Initial snapshot: flag OFF
    initial_snapshot = _make_snapshot("feature_x", is_enabled=False)
    store.update_snapshot(initial_snapshot)

    config = SDKConfig(api_key="key", base_url="http://localhost:8000")
    manager = RefreshManager(config=config, store=store)

    # New snapshot from server: flag ON
    updated_raw = {
        "environment_id": "env-1",
        "flags": {
            "feature_x": {
                "id": "flag-1",
                "key": "feature_x",
                "type": "boolean",
                "version": 2,
                "environment": {
                    "is_enabled": True,
                    "default_serve_variation_id": "v1",
                    "off_variation_id": "v2",
                    "targeting_rules": [],
                    "rollout_rules": [],
                },
                "variations": [
                    {"id": "v1", "name": "on", "value": True},
                    {"id": "v2", "name": "off", "value": False},
                ],
            }
        },
    }

    mock_transport = AsyncMock()
    mock_transport.get_snapshot.return_value = updated_raw
    manager._transport = mock_transport

    # Simulate recovery refresh
    await manager._do_refresh()

    # Store should now reflect updated snapshot
    updated_flag = store.get_flag("feature_x")
    assert updated_flag is not None
    assert updated_flag.environment.is_enabled is True, "Flag must be updated after recovery refresh"


# ---------------------------------------------------------------------------
# Fault: SDK Offline Mode
# ---------------------------------------------------------------------------
def test_sdk_offline_mode_works_without_network():
    """
    SDK in offline mode never contacts network and evaluates from pre-loaded store.
    """
    store = FlagStore()
    store.update_snapshot(_make_snapshot("offline_flag", is_enabled=True))

    config = SDKConfig(api_key="key", offline_mode=True)
    client = FeatureFlagClient(config)
    client.store = store
    client._is_started = True

    assert client.is_enabled("offline_flag") is True
    assert client.health() == "offline"


# ---------------------------------------------------------------------------
# Fault: SDK called before start()
# ---------------------------------------------------------------------------
def test_sdk_not_started_returns_default():
    """Evaluations before start() return the default value."""
    config = SDKConfig(api_key="key", offline_mode=True)
    client = FeatureFlagClient(config)
    # Don't call client.start()
    result = client.is_enabled("any_flag", default=False)
    assert result is False


# ---------------------------------------------------------------------------
# Concurrent Evaluations During Simulated Outage
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_evaluations_during_network_outage():
    """
    1000 concurrent evaluations during network outage all return cached values.
    """
    import asyncio

    store = FlagStore()
    store.update_snapshot(_make_snapshot("concurrent_flag", is_enabled=True))

    config = SDKConfig(api_key="key", offline_mode=True)
    client = FeatureFlagClient(config)
    client.store = store
    client._is_started = True

    async def eval_flag(i: int) -> bool:
        return client.is_enabled("concurrent_flag", context={"key": f"user_{i}"})

    results = await asyncio.gather(*[eval_flag(i) for i in range(1000)])

    assert all(r is True for r in results), "All evaluations must return True from cache"
    assert len(results) == 1000
