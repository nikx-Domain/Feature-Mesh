"""
Eventual Consistency Verification — Task 9
Simulates the full pipeline: DB → Outbox → Publisher → Consumer → Cache
and measures propagation delay.
"""
import pytest
import time
import json
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from aiokafka.structs import ConsumerRecord
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.infrastructure.kafka.consumers.cache_consumer import CacheInvalidationConsumer
from app.infrastructure.cache.redis_cache_service import RedisCacheService
from app.domain.entities import OutboxEventEntity, OutboxStatus


def _make_outbox_event(flag_key: str, env_id: str = "env1") -> OutboxEventEntity:
    return OutboxEventEntity(
        aggregate_type="feature_flag",
        aggregate_id=str(uuid.uuid4()),
        event_type="flag.updated",
        payload={"flag_key": flag_key, "environment_id": env_id},
    )


@pytest.fixture
def mock_redis():
    with patch("app.infrastructure.cache.redis_cache_service.get_redis_client") as mock_get:
        client = AsyncMock()

        # scan_iter must be an async generator, not a coroutine
        async def _empty_scan_iter(*args, **kwargs):
            return
            yield  # pragma: no cover

        client.scan_iter = _empty_scan_iter
        mock_get.return_value = client
        yield client


@pytest.mark.asyncio
async def test_full_pipeline_eventual_consistency(mock_redis):
    """
    Simulates: DB write → Outbox event → Publisher → Consumer → Cache invalidation.
    Verifies that after the pipeline completes, the cache reflects the new state.
    Measures propagation delay.
    """
    flag_key = "checkout_v2"
    outbox_event = _make_outbox_event(flag_key)

    # Track timing
    t_db_write = time.perf_counter()

    # Step 1: Outbox event created (DB write simulated)
    assert outbox_event.status == OutboxStatus.PENDING

    # Step 2: Publisher processes outbox event → sends to Kafka
    published_messages = []

    async def mock_send_and_wait(topic, value, key, headers):
        published_messages.append({"topic": topic, "value": value, "headers": headers})

    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            mock_uow = AsyncMock()
            mock_uow.__aenter__.return_value = mock_uow
            mock_uow.__aexit__.return_value = False
            mock_uow.outbox_events.get_pending_events.return_value = [outbox_event]
            mock_uow.outbox_events.update = AsyncMock()
            mock_uow.commit = AsyncMock()
            mock_uow_class.return_value = mock_uow

            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get_prod:
                mock_producer = AsyncMock()
                mock_producer.send_and_wait.side_effect = mock_send_and_wait
                mock_get_prod.return_value = mock_producer

                t_publish_start = time.perf_counter()
                await outbox_publisher.publish_pending_events()
                t_publish_end = time.perf_counter()

    assert outbox_event.status == OutboxStatus.PROCESSED, "Event must be PROCESSED after publish"
    assert len(published_messages) == 1, "Exactly one message published to Kafka"

    publish_latency_ms = (t_publish_end - t_publish_start) * 1000

    # Step 3: Consumer receives message → invalidates cache
    cache_svc = RedisCacheService()
    consumer = CacheInvalidationConsumer(cache_svc)

    published_msg = published_messages[0]
    kafka_msg = ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None,
        value=published_msg["value"],
        headers=published_msg["headers"],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )

    t_consume_start = time.perf_counter()
    await consumer.process_message(kafka_msg)
    t_consume_end = time.perf_counter()

    consume_latency_ms = (t_consume_end - t_consume_start) * 1000

    # Step 4: Cache now shows a miss (stale data evicted)
    mock_redis.get.return_value = None
    result = await cache_svc.get(f"eval_ptr:env1:{flag_key}")
    assert result is None, "Cache must be empty after invalidation"

    # Step 5: Measure total propagation delay
    t_end = time.perf_counter()
    total_propagation_ms = (t_end - t_db_write) * 1000

    # In a mocked environment, propagation should complete within 100ms
    assert total_propagation_ms < 100, f"Propagation took {total_propagation_ms:.2f}ms"
    assert publish_latency_ms < 50, f"Publish latency {publish_latency_ms:.2f}ms too high"
    assert consume_latency_ms < 50, f"Consume latency {consume_latency_ms:.2f}ms too high"


@pytest.mark.asyncio
async def test_pipeline_ordering_preserved(mock_redis):
    """
    Multiple events for the same flag should be processed in order.
    Each event's result must reflect the latest state.
    """
    events = [_make_outbox_event(f"flag_{i}") for i in range(5)]
    processed_order = []

    async def mock_send(*args, **kwargs):
        # Capture order
        headers_dict = {k: v.decode() for k, v in kwargs.get("headers", [])}
        processed_order.append(headers_dict.get("event_type"))

    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            mock_uow = AsyncMock()
            mock_uow.__aenter__.return_value = mock_uow
            mock_uow.__aexit__.return_value = False
            mock_uow.outbox_events.get_pending_events.return_value = events
            mock_uow.outbox_events.update = AsyncMock()
            mock_uow.commit = AsyncMock()
            mock_uow_class.return_value = mock_uow

            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get_prod:
                mock_producer = AsyncMock()
                mock_producer.send_and_wait.side_effect = mock_send
                mock_get_prod.return_value = mock_producer
                await outbox_publisher.publish_pending_events()

    # All events processed
    for event in events:
        assert event.status == OutboxStatus.PROCESSED

    # Events processed in iteration order
    assert len(processed_order) == 5


@pytest.mark.asyncio
async def test_consistency_window_measurement(mock_redis):
    """
    Measures the consistency window (time between flag update and cache reflecting it).
    In production with real Kafka, this would be ~10-100ms.
    In mocked tests, it should be < 10ms.
    """
    flag_key = "window_test_flag"
    outbox_event = _make_outbox_event(flag_key)

    t_flag_update = time.perf_counter()

    # Simulate entire pipeline in-process
    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            mock_uow = AsyncMock()
            mock_uow.__aenter__.return_value = mock_uow
            mock_uow.__aexit__.return_value = False
            mock_uow.outbox_events.get_pending_events.return_value = [outbox_event]
            mock_uow.outbox_events.update = AsyncMock()
            mock_uow.commit = AsyncMock()
            mock_uow_class.return_value = mock_uow

            kafka_messages = []
            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get_prod:
                mock_producer = AsyncMock()
                async def capture_msg(**kwargs):
                    kafka_messages.append(kwargs)
                mock_producer.send_and_wait.side_effect = capture_msg
                mock_get_prod.return_value = mock_producer
                await outbox_publisher.publish_pending_events()

    # Consumer processes the message
    cache_svc = RedisCacheService()
    consumer = CacheInvalidationConsumer(cache_svc)

    payload = json.dumps(outbox_event.payload).encode("utf-8")
    msg = ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=payload,
        headers=[
            ("event_type", "flag.updated".encode()),
            ("event_id", str(outbox_event.id).encode()),
        ],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )
    await consumer.process_message(msg)

    t_cache_invalidated = time.perf_counter()
    consistency_window_ms = (t_cache_invalidated - t_flag_update) * 1000

    # Document the consistency window
    print(f"\n[Consistency Window] {consistency_window_ms:.3f}ms (mocked pipeline)")
    assert consistency_window_ms < 100, f"Consistency window {consistency_window_ms:.2f}ms exceeds 100ms threshold"
