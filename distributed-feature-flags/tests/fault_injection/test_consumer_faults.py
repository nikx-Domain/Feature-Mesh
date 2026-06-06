"""
Consumer Fault Injection Tests — Task 5
Simulates processing failures, malformed messages, and consumer crashes.
Verifies graceful degradation and recovery behavior.
"""
import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from aiokafka.structs import ConsumerRecord
from app.infrastructure.kafka.consumers.cache_consumer import CacheInvalidationConsumer
from app.infrastructure.kafka.consumers.audit_consumer import AuditConsumer


def _make_msg(event_type: str, event_id: str, payload: dict, encode_error: bool = False) -> ConsumerRecord:
    value = b"INVALID{json}" if encode_error else json.dumps(payload).encode("utf-8")
    return ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=value,
        headers=[
            ("event_type", event_type.encode("utf-8")),
            ("event_id", event_id.encode("utf-8")),
        ],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )


# ---------------------------------------------------------------------------
# CacheConsumer: Fault Injection
# ---------------------------------------------------------------------------
@pytest.fixture
def cache_svc():
    return AsyncMock()


@pytest.fixture
def cache_consumer(cache_svc):
    return CacheInvalidationConsumer(cache_svc)


@pytest.mark.asyncio
async def test_cache_consumer_malformed_json_handled(cache_consumer):
    """Malformed JSON payload is silently skipped — no crash."""
    msg = _make_msg("flag.updated", str(uuid.uuid4()), {}, encode_error=True)
    await cache_consumer.process_message(msg)  # Must not raise


@pytest.mark.asyncio
async def test_cache_consumer_missing_flag_key_skipped(cache_consumer, cache_svc):
    """Event with no flag_key in payload is skipped without invalidation."""
    msg = _make_msg("flag.updated", str(uuid.uuid4()), {"other_field": "value"})
    await cache_consumer.process_message(msg)
    cache_svc.delete_pattern.assert_not_called()


@pytest.mark.asyncio
async def test_cache_consumer_cache_delete_failure_raises(cache_consumer, cache_svc):
    """Cache delete failure is re-raised (to allow retry at consumer level)."""
    cache_svc.delete_pattern.side_effect = Exception("Redis down")
    msg = _make_msg("flag.updated", str(uuid.uuid4()), {"flag_key": "test"})
    with pytest.raises(Exception):
        await cache_consumer.process_message(msg)


@pytest.mark.asyncio
async def test_cache_consumer_unknown_event_type_no_op(cache_consumer, cache_svc):
    """Unknown event types do not trigger any cache operations."""
    msg = _make_msg("flag.unknown_operation", str(uuid.uuid4()), {"flag_key": "test"})
    await cache_consumer.process_message(msg)
    # flag.created is a known type that does nothing; unknown types also do nothing
    cache_svc.delete.assert_not_called()
    cache_svc.delete_pattern.assert_not_called()


@pytest.mark.asyncio
async def test_cache_consumer_processes_after_single_failure(cache_consumer, cache_svc):
    """Consumer continues processing new events after a single failure."""
    bad_msg = _make_msg("flag.updated", "bad-id", {}, encode_error=True)
    good_msg = _make_msg("flag.updated", "good-id", {"flag_key": "my_flag"})

    # Bad message silently skipped
    await cache_consumer.process_message(bad_msg)

    # Good message processes normally
    await cache_consumer.process_message(good_msg)
    cache_svc.delete_pattern.assert_called()


# ---------------------------------------------------------------------------
# AuditConsumer: Fault Injection
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_factory():
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute.return_value = result
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.mark.asyncio
async def test_audit_consumer_no_headers_skipped(mock_factory):
    """Missing headers causes silent skip."""
    factory, _ = mock_factory
    msg = ConsumerRecord(
        topic="flag-events", partition=0, offset=1, timestamp=1,
        timestamp_type=0, key=None, value=b'{}', headers=[],
        checksum=0, serialized_key_size=0, serialized_value_size=0,
    )
    consumer = AuditConsumer(session_factory=factory)
    await consumer.process_message(msg)  # No crash, no write


@pytest.mark.asyncio
async def test_audit_consumer_unknown_event_type_no_audit(mock_factory):
    """Unknown event types produce no audit record."""
    factory, session = mock_factory
    with patch("app.infrastructure.kafka.consumers.audit_consumer.SQLAlchemyUnitOfWork") as mock_uow_class:
        uow = AsyncMock()
        uow.audit_events = AsyncMock()
        mock_uow_class.return_value = uow
        consumer = AuditConsumer(session_factory=factory)
        payload = {"aggregate_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()), "organization_id": str(uuid.uuid4())}
        msg = _make_msg("flag.unknown_operation", str(uuid.uuid4()), payload)
        await consumer.process_message(msg)
        uow.audit_events.add.assert_not_called()


@pytest.mark.asyncio
async def test_audit_consumer_partial_payload_handled(mock_factory):
    """
    Payload missing some optional fields (user_id) should not crash the consumer.
    """
    factory, session = mock_factory
    with patch("app.infrastructure.kafka.consumers.audit_consumer.SQLAlchemyUnitOfWork") as mock_uow_class:
        uow = AsyncMock()
        uow.audit_events = AsyncMock()
        mock_uow_class.return_value = uow
        consumer = AuditConsumer(session_factory=factory)
        payload = {
            "aggregate_id": str(uuid.uuid4()),
            # No user_id
            "organization_id": str(uuid.uuid4()),
        }
        msg = _make_msg("flag.created", str(uuid.uuid4()), payload)
        await consumer.process_message(msg)
        uow.audit_events.add.assert_called_once()
