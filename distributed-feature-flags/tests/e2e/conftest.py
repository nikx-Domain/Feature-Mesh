"""
E2E conftest — patches Redis and Kafka so E2E tests run without real external services.
The SQLite DB is used as-is (already configured in settings for test env).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def patch_external_services():
    """
    Patches all external service initializations for E2E tests:
    - Redis: mocked pool + client (returns None for all cache ops → DB fallback)
    - Kafka producer: mocked (no-op sends)
    - Outbox publisher: prevented from starting background loop
    - Cache/Audit consumers: prevented from starting Kafka consumers
    """
    mock_redis_client = AsyncMock()
    mock_redis_client.get.return_value = None  # Cache miss → DB fallback
    mock_redis_client.set.return_value = True
    mock_redis_client.delete.return_value = 1
    mock_redis_client.exists.return_value = False

    async def _empty_scan(*args, **kwargs):
        return
        yield  # pragma: no cover

    mock_redis_client.scan_iter = _empty_scan

    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    with patch("app.infrastructure.redis.client.init_redis", new=AsyncMock()):
        with patch("app.infrastructure.redis.client.close_redis", new=AsyncMock()):
            with patch("app.infrastructure.redis.client.get_redis_client", return_value=mock_redis_client):
                with patch("app.infrastructure.cache.redis_cache_service.get_redis_client", return_value=mock_redis_client):
                    with patch("app.infrastructure.kafka.client.init_kafka_producer", new=AsyncMock()):
                        with patch("app.infrastructure.kafka.client.close_kafka_producer", new=AsyncMock()):
                            with patch("app.infrastructure.kafka.client.get_kafka_producer", return_value=mock_producer):
                                with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer", return_value=mock_producer):
                                    with patch("app.infrastructure.background.outbox_publisher.OutboxPublisher.start", new=AsyncMock()):
                                        with patch("app.infrastructure.background.outbox_publisher.OutboxPublisher.stop", new=AsyncMock()):
                                            with patch("app.infrastructure.kafka.consumers.cache_consumer.CacheInvalidationConsumer.start", new=AsyncMock()):
                                                with patch("app.infrastructure.kafka.consumers.cache_consumer.CacheInvalidationConsumer.stop", new=AsyncMock()):
                                                    with patch("app.infrastructure.kafka.consumers.audit_consumer.AuditConsumer.start", new=AsyncMock()):
                                                        with patch("app.infrastructure.kafka.consumers.audit_consumer.AuditConsumer.stop", new=AsyncMock()):
                                                            yield
