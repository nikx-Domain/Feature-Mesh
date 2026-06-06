import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from redis.exceptions import RedisError
from app.infrastructure.cache.redis_cache_service import RedisCacheService

@pytest.fixture
def mock_redis_client():
    with patch('app.infrastructure.cache.redis_cache_service.get_redis_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        yield mock_client

@pytest.mark.asyncio
async def test_redis_cache_hit(mock_redis_client):
    mock_redis_client.get.return_value = b'test_value'
    service = RedisCacheService()
    
    val = await service.get("test_key")
    assert val == "test_value"
    mock_redis_client.get.assert_called_once_with("test_key")

@pytest.mark.asyncio
async def test_redis_cache_miss(mock_redis_client):
    mock_redis_client.get.return_value = None
    service = RedisCacheService()
    
    val = await service.get("test_key")
    assert val is None

@pytest.mark.asyncio
async def test_redis_failure_graceful_degradation(mock_redis_client):
    # Simulate Redis connection drop or timeout
    mock_redis_client.get.side_effect = RedisError("Connection lost")
    service = RedisCacheService()
    
    # Must NOT raise the exception, should gracefully return None
    val = await service.get("test_key")
    assert val is None

@pytest.mark.asyncio
async def test_redis_cache_rebuild(mock_redis_client):
    service = RedisCacheService()
    await service.set("test_key", "test_value", expire_seconds=60)
    mock_redis_client.set.assert_called_once_with("test_key", "test_value", ex=60)

@pytest.mark.asyncio
async def test_redis_set_failure(mock_redis_client):
    mock_redis_client.set.side_effect = RedisError("OOM")
    service = RedisCacheService()
    # Must not raise
    await service.set("test_key", "test_value")
    mock_redis_client.set.assert_called_once()
