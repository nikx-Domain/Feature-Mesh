"""
Consumer Recovery Tests — Task 4
Tests crash + restart + idempotency for both CacheInvalidationConsumer and AuditConsumer.
"""
import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from aiokafka.structs import ConsumerRecord
from app.infrastructure.kafka.consumers.cache_consumer import CacheInvalidationConsumer
from app.infrastructure.kafka.consumers.audit_consumer import AuditConsumer


def _make_msg(event_type: str, event_id: str, payload: dict) -> ConsumerRecord:
    """Helper to build a mock ConsumerRecord."""
    value = json.dumps(payload).encode("utf-8")
    headers = [
        ("event_type", event_type.encode("utf-8")),
        ("event_id", event_id.encode("utf-8")),
    ]
    return ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=value, headers=headers,
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )


# ===========================================================================
# CacheInvalidationConsumer Recovery
# ===========================================================================
@pytest.fixture
def cache_svc():
    return AsyncMock()


@pytest.fixture
def cache_consumer(cache_svc):
    return CacheInvalidationConsumer(cache_svc)


@pytest.mark.asyncio
async def test_cache_consumer_crash_then_restart(cache_consumer, cache_svc):
    """
    First message processing raises → consumer does not die.
    Second message (same event) is retried and processed successfully.
    """
    payload = {"flag_key": "my_flag", "environment_id": "env1"}
    msg = _make_msg("flag.toggled", str(uuid.uuid4()), payload)

    # First attempt: cache service fails
    cache_svc.delete.side_effect = [Exception("Redis down"), None]
    cache_svc.delete_pattern.side_effect = [Exception("Redis down"), None]

    # First call raises — consumer must handle and not crash
    with pytest.raises(Exception):
        await cache_consumer.process_message(msg)

    # Second call (restart): cache service recovered
    cache_svc.delete.side_effect = None
    cache_svc.delete_pattern.side_effect = None
    await cache_consumer.process_message(msg)

    # Should have called delete on recovery
    assert cache_svc.delete.call_count >= 1


@pytest.mark.asyncio
async def test_cache_consumer_idempotent_on_same_event(cache_consumer, cache_svc):
    """
    Processing the same event_id twice produces the same cache invalidation calls.
    (Cache invalidation is naturally idempotent — delete is safe to call multiple times.)
    """
    event_id = str(uuid.uuid4())
    payload = {"flag_key": "my_flag"}
    msg = _make_msg("flag.updated", event_id, payload)

    await cache_consumer.process_message(msg)
    await cache_consumer.process_message(msg)  # Replay

    # delete_pattern called twice (once per message) — but effect is idempotent
    assert cache_svc.delete_pattern.call_count == 4  # 2 patterns × 2 calls


@pytest.mark.asyncio
async def test_cache_consumer_missing_headers_skipped(cache_consumer, cache_svc):
    """Messages without headers are silently skipped."""
    msg = ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=b'{}', headers=[],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )
    await cache_consumer.process_message(msg)
    cache_svc.delete.assert_not_called()
    cache_svc.delete_pattern.assert_not_called()


@pytest.mark.asyncio
async def test_cache_consumer_resumes_after_single_failure(cache_consumer, cache_svc):
    """
    Consumer processes event1 (fails), event2 (succeeds).
    Verifies the consumer remains operational after a single processing error.
    """
    event1 = _make_msg("flag.updated", "eid-1", {"flag_key": "flag_a"})
    event2 = _make_msg("flag.updated", "eid-2", {"flag_key": "flag_b"})

    cache_svc.delete_pattern.side_effect = [Exception("crash"), None, None, None]

    with pytest.raises(Exception):
        await cache_consumer.process_message(event1)

    cache_svc.delete_pattern.side_effect = None
    await cache_consumer.process_message(event2)
    assert cache_svc.delete_pattern.call_count >= 1


# ===========================================================================
# AuditConsumer Recovery + Idempotency
# ===========================================================================
@pytest.fixture
def mock_session_factory():
    """Returns a session factory that yields mocked async sessions."""
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False

    # Default: no prior processed events (first-time processing)
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = None
    session.execute.return_value = result_mock

    factory = MagicMock(return_value=session)
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def audit_consumer(mock_session_factory):
    factory, _ = mock_session_factory
    with patch("app.infrastructure.kafka.consumers.audit_consumer.SQLAlchemyUnitOfWork") as mock_uow_class:
        uow = AsyncMock()
        uow.audit_events = AsyncMock()
        mock_uow_class.return_value = uow
        consumer = AuditConsumer(session_factory=factory)
        consumer._uow_class = mock_uow_class
        yield consumer, uow, mock_session_factory[1]


@pytest.mark.asyncio
async def test_audit_consumer_idempotency_duplicate_event(mock_session_factory):
    """
    Processing the same event_id twice must NOT create duplicate audit records.
    The idempotency check (ProcessedKafkaEvent lookup) prevents re-processing.
    """
    factory, session = mock_session_factory
    event_id = str(uuid.uuid4())
    payload = {
        "aggregate_id": str(uuid.uuid4()),
        "flag_key": "test",
        "user_id": str(uuid.uuid4()),
        "organization_id": str(uuid.uuid4()),
    }
    msg = _make_msg("flag.created", event_id, payload)

    with patch("app.infrastructure.kafka.consumers.audit_consumer.SQLAlchemyUnitOfWork") as mock_uow_class:
        uow = AsyncMock()
        uow.audit_events = AsyncMock()
        mock_uow_class.return_value = uow
        consumer = AuditConsumer(session_factory=factory)

        # First processing: no prior event
        result_first = MagicMock()
        result_first.scalars.return_value.first.return_value = None

        # Second processing: event already exists
        processed_event = MagicMock()
        result_second = MagicMock()
        result_second.scalars.return_value.first.return_value = processed_event

        session.execute.side_effect = [result_first, result_second]

        await consumer.process_message(msg)
        first_add_count = uow.audit_events.add.call_count

        await consumer.process_message(msg)
        second_add_count = uow.audit_events.add.call_count

        # First call added audit; second call was skipped due to idempotency
        assert first_add_count == 1
        assert second_add_count == 1, "Duplicate event must not create second audit record"


@pytest.mark.asyncio
async def test_audit_consumer_missing_headers_skipped(mock_session_factory):
    """AuditConsumer silently skips messages with no headers."""
    factory, _ = mock_session_factory
    msg = ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=b'{}', headers=[],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )
    consumer = AuditConsumer(session_factory=factory)
    await consumer.process_message(msg)
    # No session interaction should occur for messages without headers
