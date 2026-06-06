"""
Redis Fault Injection Tests — Task 5
Simulates: Redis Timeout, Connection Error, OOM, Pattern Scan failure.
Verifies: graceful degradation, no exception propagation, retry/recovery.
"""
import pytest
from unittest.mock import patch, AsyncMock
from redis.exceptions import (
    RedisError,
    TimeoutError as RedisTimeoutError,
    ConnectionError as RedisConnectionError,
    ResponseError,
)
from app.infrastructure.cache.redis_cache_service import RedisCacheService


@pytest.fixture
def redis_client():
    with patch("app.infrastructure.cache.redis_cache_service.get_redis_client") as mock_get:
        client = AsyncMock()
        mock_get.return_value = client
        yield client


# ---------------------------------------------------------------------------
# Fault: Redis Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_timeout_get_returns_none(redis_client):
    """GET during timeout degrades to None — no exception propagated."""
    redis_client.get.side_effect = RedisTimeoutError("socket timeout")
    svc = RedisCacheService()
    result = await svc.get("key")
    assert result is None


@pytest.mark.asyncio
async def test_redis_timeout_set_silenced(redis_client):
    """SET during timeout is silently swallowed — no exception propagated."""
    redis_client.set.side_effect = RedisTimeoutError("timeout")
    svc = RedisCacheService()
    await svc.set("key", "value")  # Must not raise


@pytest.mark.asyncio
async def test_redis_timeout_delete_silenced(redis_client):
    """DELETE during timeout is silently swallowed."""
    redis_client.delete.side_effect = RedisTimeoutError("timeout")
    svc = RedisCacheService()
    await svc.delete("key")  # Must not raise


# ---------------------------------------------------------------------------
# Fault: Connection Error (Network Partition)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_connection_refused_get_returns_none(redis_client):
    """GET when connection refused returns None."""
    redis_client.get.side_effect = RedisConnectionError("connection refused")
    svc = RedisCacheService()
    result = await svc.get("key")
    assert result is None


@pytest.mark.asyncio
async def test_redis_connection_refused_exists_returns_false(redis_client):
    """EXISTS when connection refused returns False."""
    redis_client.exists.side_effect = RedisConnectionError("connection refused")
    svc = RedisCacheService()
    result = await svc.exists("key")
    assert result is False


# ---------------------------------------------------------------------------
# Fault: OOM / Server Error
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_oom_set_silenced(redis_client):
    """SET during OOM is silently swallowed."""
    redis_client.set.side_effect = ResponseError("OOM command not allowed when used memory > 'maxmemory'")
    svc = RedisCacheService()
    await svc.set("key", "value")  # Must not raise


# ---------------------------------------------------------------------------
# Fault: Pattern Scan Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_scan_iter_failure_silenced(redis_client):
    """delete_pattern scan failure is silenced."""
    async def failing_scan(*args, **kwargs):
        raise RedisError("scan failed")
        yield  # make it an async generator
    redis_client.scan_iter = failing_scan
    svc = RedisCacheService()
    await svc.delete_pattern("eval:*")  # Must not raise


# ---------------------------------------------------------------------------
# Recovery: Automatic recovery on next call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_recovers_after_timeout(redis_client):
    """Service automatically recovers — no circuit breaker holds state."""
    svc = RedisCacheService()

    redis_client.get.side_effect = RedisTimeoutError("timeout")
    result_1 = await svc.get("key")
    assert result_1 is None

    redis_client.get.side_effect = None
    redis_client.get.return_value = b"value_after_recovery"
    result_2 = await svc.get("key")
    assert result_2 == "value_after_recovery"


@pytest.mark.asyncio
async def test_redis_recovers_after_connection_error(redis_client):
    """Service recovers from connection error on next successful call."""
    svc = RedisCacheService()

    redis_client.get.side_effect = RedisConnectionError("lost")
    await svc.get("key")

    redis_client.get.side_effect = None
    redis_client.get.return_value = b"recovered"
    assert await svc.get("key") == "recovered"


# ---------------------------------------------------------------------------
# Retry Behavior: Multiple consecutive failures then recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_multiple_failures_then_recovery(redis_client):
    """
    Simulate 3 consecutive failures followed by a recovery.
    All failures must degrade gracefully; recovery call must succeed.
    """
    svc = RedisCacheService()

    for _ in range(3):
        redis_client.get.side_effect = RedisTimeoutError("timeout")
        result = await svc.get("key")
        assert result is None

    redis_client.get.side_effect = None
    redis_client.get.return_value = b"ok"
    result = await svc.get("key")
    assert result == "ok"
