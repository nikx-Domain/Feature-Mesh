"""
Kafka Recovery Tests — Task 2
Tests full lifecycle: publisher working → Kafka failure → outbox accumulation
→ Kafka recovery → backlog processing → eventual consistency restored.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.domain.entities import OutboxEventEntity, OutboxStatus


@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    uow.outbox_events.get_pending_events = AsyncMock(return_value=[])
    uow.outbox_events.update = AsyncMock()
    uow.commit = AsyncMock()
    return uow


@pytest.fixture
def mock_infra(mock_uow):
    """Patches both SessionLocal and SQLAlchemyUnitOfWork to inject mocks."""
    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            mock_uow_class.return_value = mock_uow
            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_producer_getter:
                producer = AsyncMock()
                mock_producer_getter.return_value = producer
                yield mock_uow, producer


def _make_event(**kwargs):
    defaults = dict(aggregate_type="feature_flag", aggregate_id="123", event_type="flag.created", payload={"flag_key": "test"})
    defaults.update(kwargs)
    return OutboxEventEntity(**defaults)


# ---------------------------------------------------------------------------
# Scenario 1: Normal Operation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_normal_publish(mock_infra):
    """Events in outbox are published and marked PROCESSED."""
    mock_uow, producer = mock_infra
    event = _make_event()
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    await outbox_publisher.publish_pending_events()

    producer.send_and_wait.assert_called_once()
    assert event.status == OutboxStatus.PROCESSED
    mock_uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 2: Kafka Failure → Outbox Growth
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_failure_event_remains_pending(mock_infra):
    """When Kafka is down, event stays PENDING (retry_count incremented)."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=0)
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    producer.send_and_wait.side_effect = Exception("Kafka broker unavailable")

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.PENDING, "Event must stay PENDING when Kafka is down"
    assert event.retry_count == 1, "Retry count must increment"
    mock_uow.outbox_events.update.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_kafka_failure_multiple_events_all_remain_pending(mock_infra):
    """Multiple events all remain PENDING during sustained Kafka outage."""
    mock_uow, producer = mock_infra
    events = [_make_event(aggregate_id=str(i)) for i in range(5)]
    mock_uow.outbox_events.get_pending_events.return_value = events

    producer.send_and_wait.side_effect = Exception("Kafka down")

    await outbox_publisher.publish_pending_events()

    for ev in events:
        assert ev.status == OutboxStatus.PENDING
        assert ev.retry_count == 1


@pytest.mark.asyncio
async def test_kafka_failure_exceeds_retry_limit(mock_infra):
    """After >5 retries, event is marked FAILED."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=5)
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    producer.send_and_wait.side_effect = Exception("persistent failure")

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.FAILED, "Event exceeding retry limit must be FAILED"


# ---------------------------------------------------------------------------
# Scenario 3: Kafka Recovery → Backlog Processing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_recovery_processes_backlog(mock_infra):
    """
    First iteration: Kafka fails → events remain PENDING.
    Second iteration: Kafka recovers → events are processed.
    """
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=0)
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    # First pass: Kafka down
    producer.send_and_wait.side_effect = Exception("unavailable")
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PENDING
    assert event.retry_count == 1

    # Reset event to PENDING (simulating it reappears in next poll)
    event.retry_count = 1

    # Second pass: Kafka recovers
    producer.send_and_wait.side_effect = None
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PROCESSED
    assert event.retry_count == 1  # No additional increment after success


@pytest.mark.asyncio
async def test_kafka_partial_recovery(mock_infra):
    """First event succeeds, second fails — partial batch handling."""
    mock_uow, producer = mock_infra
    event1 = _make_event(aggregate_id="1")
    event2 = _make_event(aggregate_id="2")
    mock_uow.outbox_events.get_pending_events.return_value = [event1, event2]

    # event1 succeeds, event2 fails
    producer.send_and_wait.side_effect = [None, Exception("timeout")]

    await outbox_publisher.publish_pending_events()

    assert event1.status == OutboxStatus.PROCESSED
    assert event2.status == OutboxStatus.PENDING
    assert event2.retry_count == 1


# ---------------------------------------------------------------------------
# Scenario 4: No event loss verification
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_no_event_loss_on_failure(mock_infra):
    """
    Events that fail to publish are NOT removed from outbox.
    The update call preserves them as PENDING for next iteration.
    """
    mock_uow, producer = mock_infra
    events = [_make_event(aggregate_id=str(i)) for i in range(3)]
    mock_uow.outbox_events.get_pending_events.return_value = events

    producer.send_and_wait.side_effect = Exception("partition error")

    await outbox_publisher.publish_pending_events()

    # All events should have been updated (kept in outbox, not dropped)
    assert mock_uow.outbox_events.update.call_count == 3
    for ev in events:
        assert ev.status == OutboxStatus.PENDING  # Not lost


# ---------------------------------------------------------------------------
# Scenario 5: No producer (Kafka not initialized)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_no_producer_skips_gracefully():
    """If Kafka producer is not initialized, publishing is skipped without error."""
    with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get:
        mock_get.return_value = None  # Kafka not initialized
        # Should not raise
        await outbox_publisher.publish_pending_events()
