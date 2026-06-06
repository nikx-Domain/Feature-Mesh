import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError
from app.infrastructure.cache.redis_cache_service import RedisCacheService
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.domain.entities import OutboxEventEntity, OutboxStatus
from sdk.client.client import FeatureFlagClient
from sdk.config.config import SDKConfig

@pytest.mark.asyncio
async def test_redis_timeout_recovery():
    """
    Tests that a Redis Timeout degrades gracefully (returning None) 
    and that a subsequent successful call recovers automatically.
    """
    with patch('app.infrastructure.cache.redis_cache_service.get_redis_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        service = RedisCacheService()
        
        # 1. Simulate Redis Timeout
        mock_client.get.side_effect = RedisTimeoutError("Connection timed out")
        
        val = await service.get("test_key")
        assert val is None # Graceful degradation
        
        # 2. Simulate Recovery
        mock_client.get.side_effect = None
        mock_client.get.return_value = b'recovered_value'
        
        val_recovered = await service.get("test_key")
        assert val_recovered == "recovered_value"

@pytest.mark.asyncio
async def test_kafka_timeout_recovery():
    """
    Tests that Kafka Publisher timeouts do not crash the outbox loop,
    and events are retried automatically until they succeed.
    """
    uow = AsyncMock()
    event = OutboxEventEntity(aggregate_type="test", aggregate_id="123", event_type="flag-events", payload={"test": "data"}, retry_count=0)
    
    # 1. Returns event on first loop, empty on subsequent
    uow.outbox_events.get_pending_events.side_effect = [[event], [event], []]
    
    with patch('app.infrastructure.background.outbox_publisher.SessionLocal') as session_local:
        with patch('app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork') as mock_uow_class:
            mock_uow_class.return_value = uow
            with patch('app.infrastructure.background.outbox_publisher.get_kafka_producer') as mock_get_producer:
                producer = AsyncMock()
                mock_get_producer.return_value = producer
                
                # 1. First publish fails with Timeout
                producer.send_and_wait.side_effect = [Exception("Kafka Timeout"), None] # Fail then succeed
                
                with patch('app.infrastructure.background.outbox_publisher.asyncio.sleep', AsyncMock(side_effect=[None, None, Exception("Stop Loop")])):
                    try:
                        outbox_publisher._running = True
                        await outbox_publisher._run_loop()
                    except Exception as e:
                        assert str(e) == "Stop Loop"
                        
                # Event should be updated twice (once failed, once success)
                assert uow.outbox_events.update.call_count == 2
                assert event.status == OutboxStatus.PROCESSED
                assert event.retry_count == 1

@pytest.mark.asyncio
@patch("sdk.transport.client.httpx.AsyncClient.get")
async def test_sdk_refresh_failure_graceful_degradation(mock_get):
    """
    Tests that an SDK background refresh failure (Network Partition) 
    retains the existing cache and does not crash the client.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "environment_id": "env1",
        "flags": {
            "test": {
                "id": "1", "key": "test", "type": "boolean", "version": 1,
                "environment": {
                    "is_enabled": True, "default_serve_variation_id": "v1", "off_variation_id": "v2",
                    "targeting_rules": [], "rollout_rules": []
                },
                "variations": [
                    {"id": "v1", "name": "true", "value": True},
                    {"id": "v2", "name": "false", "value": False}
                ]
            }
        }
    }
    mock_response.raise_for_status.return_value = None
    
    # 1. Bootstrap succeeds
    # 2. First refresh hits network partition
    mock_get.side_effect = [mock_response, Exception("Network Partition")]
    
    config = SDKConfig(api_key="test", refresh_interval=0.1)
    client = FeatureFlagClient(config)
    client.start()
    
    assert client.health() == "healthy"
    assert client.is_enabled("test") is True
    
    # Allow refresh to trigger
    await asyncio.sleep(0.3)
    
    # Client should remain healthy based on the old cache
    assert client.health() == "healthy"
    assert client.is_enabled("test") is True
    
    client.shutdown()
