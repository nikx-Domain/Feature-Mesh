"""
Outbox Publisher Fault Injection Tests — Task 5
Simulates: publish failure, crash mid-batch, retry limit exceeded,
and idempotency on re-delivery.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.domain.entities import OutboxEventEntity, OutboxStatus


def _make_event(**kwargs):
    defaults = dict(
        aggregate_type="feature_flag",
        aggregate_id="fault-id",
        event_type="flag.created",
        payload={"flag_key": "fault_flag"},
    )
    defaults.update(kwargs)
    return OutboxEventEntity(**defaults)


@pytest.fixture
def mock_infra():
    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            uow = AsyncMock()
            uow.__aenter__.return_value = uow
            uow.__aexit__.return_value = False
            uow.outbox_events.get_pending_events = AsyncMock(return_value=[])
            uow.outbox_events.update = AsyncMock()
            uow.commit = AsyncMock()
            mock_uow_class.return_value = uow
            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get_prod:
                producer = AsyncMock()
                mock_get_prod.return_value = producer
                yield uow, producer


# ---------------------------------------------------------------------------
# Fault: Publish Failure (first attempt)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_publish_failure_increments_retry(mock_infra):
    """Publish failure increments retry_count and keeps event PENDING."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=0)
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = Exception("publish error")

    await outbox_publisher.publish_pending_events()

    assert event.retry_count == 1
    assert event.status == OutboxStatus.PENDING
    mock_uow.outbox_events.update.assert_called_once_with(event)


# ---------------------------------------------------------------------------
# Fault: Crash Mid-Batch
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_crash_mid_batch_partial_commit(mock_infra):
    """
    Events before crash are processed; events after remain PENDING.
    Simulates publisher crash between event 1 (ok) and event 2 (fail).
    """
    mock_uow, producer = mock_infra
    ev1 = _make_event(aggregate_id="1")
    ev2 = _make_event(aggregate_id="2")
    mock_uow.outbox_events.get_pending_events.return_value = [ev1, ev2]
    producer.send_and_wait.side_effect = [None, Exception("crash")]

    await outbox_publisher.publish_pending_events()

    assert ev1.status == OutboxStatus.PROCESSED
    assert ev2.status == OutboxStatus.PENDING
    assert ev2.retry_count == 1


# ---------------------------------------------------------------------------
# Fault: Retry Limit Exceeded
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_retry_limit_marks_failed(mock_infra):
    """Events with retry_count > 5 are marked FAILED."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=5)  # Will be incremented to 6 > 5
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = Exception("permanent failure")

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.FAILED
    assert event.retry_count == 6


# ---------------------------------------------------------------------------
# Fault: Empty outbox (no-op)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_empty_is_noop(mock_infra):
    """Empty outbox results in no Kafka messages published."""
    mock_uow, producer = mock_infra
    mock_uow.outbox_events.get_pending_events.return_value = []

    await outbox_publisher.publish_pending_events()

    producer.send_and_wait.assert_not_called()


# ---------------------------------------------------------------------------
# Fault: Idempotent Publish
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_publish_idempotent_on_retry(mock_infra):
    """
    Publishing the same event twice (due to crash + restart) sends two Kafka messages.
    The consumer's idempotency check prevents duplicate audit records.
    This test verifies the publisher correctly re-sends after a simulated restart.
    """
    mock_uow, producer = mock_infra
    event = _make_event()
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    # First publish
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PROCESSED

    # Simulate event reappearing as PENDING (crash before DB commit)
    event.status = OutboxStatus.PENDING

    # Second publish (retry)
    await outbox_publisher.publish_pending_events()
    assert producer.send_and_wait.call_count == 2


# ---------------------------------------------------------------------------
# Fault: Commit failure — events remain PENDING
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbox_commit_failure_does_not_lose_events(mock_infra):
    """
    If commit fails after successful publish, events will be reprocessed on restart.
    This verifies the at-least-once delivery guarantee.
    """
    mock_uow, producer = mock_infra
    event = _make_event()
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    mock_uow.commit.side_effect = Exception("DB commit failed")

    with pytest.raises(Exception):
        await outbox_publisher.publish_pending_events()

    # Event was sent to Kafka but DB not committed → will be re-sent on restart
    # (At-least-once delivery: consumer must handle duplicates via idempotency)
    assert producer.send_and_wait.call_count == 1
