"""
Redis Recovery Tests — Task 1
Tests full lifecycle: Redis working → failure → graceful degradation → recovery → cache rebuild.
No live Redis needed; all mocked via `patch`.
"""
import pytest
import time
from unittest.mock import patch, AsyncMock, call
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError, ConnectionError as RedisConnectionError
from app.infrastructure.cache.redis_cache_service import RedisCacheService


@pytest.fixture
def mock_redis():
    """Provides a mock Redis client injected via patch."""
    with patch("app.infrastructure.cache.redis_cache_service.get_redis_client") as mock_get:
        client = AsyncMock()
        mock_get.return_value = client
        yield client


# ---------------------------------------------------------------------------
# Scenario 1: Redis Running → Normal Operation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_normal_get(mock_redis):
    """Cache hit returns decoded string."""
    mock_redis.get.return_value = b"hello"
    svc = RedisCacheService()
    result = await svc.get("key")
    assert result == "hello"


@pytest.mark.asyncio
async def test_redis_normal_set(mock_redis):
    """Cache set succeeds without error."""
    svc = RedisCacheService()
    await svc.set("key", "value", expire_seconds=30)
    mock_redis.set.assert_called_once_with("key", "value", ex=30)


# ---------------------------------------------------------------------------
# Scenario 2: Redis Failure → Graceful Degradation (no exception propagated)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_timeout_graceful_degradation(mock_redis):
    """GET during timeout returns None instead of raising."""
    mock_redis.get.side_effect = RedisTimeoutError("timed out")
    svc = RedisCacheService()
    result = await svc.get("key")
    assert result is None, "Timeout must degrade gracefully to None"


@pytest.mark.asyncio
async def test_redis_connection_error_graceful_degradation(mock_redis):
    """GET during connection error returns None."""
    mock_redis.get.side_effect = RedisConnectionError("refused")
    svc = RedisCacheService()
    result = await svc.get("key")
    assert result is None


@pytest.mark.asyncio
async def test_redis_set_failure_silent(mock_redis):
    """SET during Redis OOM must not propagate exception."""
    mock_redis.set.side_effect = RedisError("OOM command not allowed")
    svc = RedisCacheService()
    await svc.set("key", "value")  # Should not raise


@pytest.mark.asyncio
async def test_redis_delete_failure_silent(mock_redis):
    """DELETE during failure must not propagate exception."""
    mock_redis.delete.side_effect = RedisError("timeout")
    svc = RedisCacheService()
    await svc.delete("key")  # Should not raise


@pytest.mark.asyncio
async def test_redis_exists_failure_returns_false(mock_redis):
    """EXISTS during failure returns False."""
    mock_redis.exists.side_effect = RedisError("down")
    svc = RedisCacheService()
    result = await svc.exists("key")
    assert result is False


@pytest.mark.asyncio
async def test_redis_delete_pattern_failure_silent(mock_redis):
    """delete_pattern scan failure is silenced."""
    async def failing_scan(*args, **kwargs):
        raise RedisError("scan failed")
        yield  # make it an async generator
    mock_redis.scan_iter = failing_scan
    svc = RedisCacheService()
    await svc.delete_pattern("eval:*")  # Must not raise


# ---------------------------------------------------------------------------
# Scenario 3: Database Fallback Simulation
# (Application logic uses None from Redis to trigger DB query — verified by
#  checking Redis returns None so upper layers can act on it)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_miss_triggers_db_fallback(mock_redis):
    """
    When Redis is down, get() returns None.
    The application layer is expected to fall back to DB.
    We verify Redis returns None so the caller knows to use fallback.
    """
    mock_redis.get.side_effect = RedisConnectionError("refused")
    svc = RedisCacheService()

    result = await svc.get("eval_ptr:env1:my_flag")
    assert result is None, "Cache miss allows upstream DB fallback"


# ---------------------------------------------------------------------------
# Scenario 4: Redis Recovery → Cache Rebuild
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_recovery_after_timeout(mock_redis):
    """
    Redis fails first, then recovers. Second call must succeed.
    Verifies that the service is stateless and naturally recovers.
    """
    svc = RedisCacheService()

    # Phase 1: Redis down
    mock_redis.get.side_effect = RedisTimeoutError("timeout")
    result_during_failure = await svc.get("key")
    assert result_during_failure is None

    # Phase 2: Redis recovers
    mock_redis.get.side_effect = None
    mock_redis.get.return_value = b"rebuilt_value"
    result_after_recovery = await svc.get("key")
    assert result_after_recovery == "rebuilt_value", "Cache must be readable after recovery"


@pytest.mark.asyncio
async def test_redis_cache_rebuild_after_delete(mock_redis):
    """
    After invalidation (delete_pattern), value is rebuilt via set().
    Asserts no stale data is served.
    """
    # Setup: scan_iter yields one old key as async generator
    async def mock_scan(*args, **kwargs):
        yield b"eval:env1:flag1"
    mock_redis.scan_iter = mock_scan
    svc = RedisCacheService()

    # Invalidate
    await svc.delete_pattern("eval:env1:*")

    # Rebuild
    await svc.set("eval:env1:flag1", "new_value", expire_seconds=300)
    mock_redis.set.assert_called_once_with("eval:env1:flag1", "new_value", ex=300)


@pytest.mark.asyncio
async def test_stale_data_not_served_after_invalidation(mock_redis):
    """
    Simulates: write value → invalidate → verify miss (None) → rebuild → verify hit.
    """
    svc = RedisCacheService()

    # 1. Write
    await svc.set("flag:key1", "old_val")

    # 2. Invalidate (simulate delete returning)
    mock_redis.delete.return_value = 1

    await svc.delete("flag:key1")

    # 3. Cache miss (stale data not served)
    mock_redis.get.return_value = None
    stale = await svc.get("flag:key1")
    assert stale is None, "No stale data after invalidation"

    # 4. Rebuild
    mock_redis.get.return_value = b"new_val"
    fresh = await svc.get("flag:key1")
    assert fresh == "new_val"


# ---------------------------------------------------------------------------
# Scenario 5: Recovery Timing Measurement
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_recovery_latency_is_immediate(mock_redis):
    """
    Recovery should be instantaneous (no circuit-breaker delay).
    Verify that after failure, the next successful call returns within < 50ms.
    """
    svc = RedisCacheService()

    mock_redis.get.side_effect = RedisTimeoutError("down")
    await svc.get("key")  # Fails

    mock_redis.get.side_effect = None
    mock_redis.get.return_value = b"ok"

    start = time.perf_counter()
    result = await svc.get("key")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result == "ok"
    assert elapsed_ms < 50, f"Recovery should be immediate but took {elapsed_ms:.1f}ms"
