"""
Kafka Fault Injection Tests — Task 5
Simulates: Kafka Timeout, Broker unavailable, Partition error, Producer not initialized.
Verifies: no event loss, retry behavior, graceful degradation.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.domain.entities import OutboxEventEntity, OutboxStatus


def _make_event(**kwargs):
    defaults = dict(
        aggregate_type="feature_flag",
        aggregate_id="test-id",
        event_type="flag.updated",
        payload={"flag_key": "test_flag"},
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
# Fault: Kafka Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_timeout_event_retried(mock_infra):
    """Kafka timeout keeps event PENDING for retry."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=0)
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = TimeoutError("Kafka broker timeout")

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.PENDING
    assert event.retry_count == 1


# ---------------------------------------------------------------------------
# Fault: Broker Unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_broker_unavailable_increments_retry(mock_infra):
    """Broker unavailable increments retry count without losing event."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=2)
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = Exception("broker not available")

    await outbox_publisher.publish_pending_events()

    assert event.retry_count == 3
    assert event.status == OutboxStatus.PENDING


# ---------------------------------------------------------------------------
# Fault: Persistent failure → FAILED status
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_persistent_failure_marks_failed(mock_infra):
    """After >5 retries, event is marked FAILED and not retried infinitely."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=5)
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = Exception("persistent error")

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.FAILED


# ---------------------------------------------------------------------------
# Fault: Network Partition — Producer not initialized
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_producer_not_initialized_skips():
    """No producer → publish is skipped without error or event loss."""
    with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get:
        mock_get.return_value = None
        # Should not raise, no events consumed
        await outbox_publisher.publish_pending_events()


# ---------------------------------------------------------------------------
# Fault: Partial Batch Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_partial_batch_no_event_loss(mock_infra):
    """When some events fail and others succeed, no events are lost."""
    mock_uow, producer = mock_infra
    success_event = _make_event(aggregate_id="success")
    fail_event = _make_event(aggregate_id="fail")
    mock_uow.outbox_events.get_pending_events.return_value = [success_event, fail_event]
    producer.send_and_wait.side_effect = [None, Exception("fail")]

    await outbox_publisher.publish_pending_events()

    assert success_event.status == OutboxStatus.PROCESSED
    assert fail_event.status == OutboxStatus.PENDING  # Still in outbox, not lost
    assert fail_event.retry_count == 1


# ---------------------------------------------------------------------------
# Recovery: Kafka recovers after failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_recovery_after_broker_down(mock_infra):
    """Publisher recovers automatically when Kafka comes back."""
    mock_uow, producer = mock_infra
    event = _make_event(retry_count=1)
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    # First call: Kafka down
    producer.send_and_wait.side_effect = Exception("broker down")
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PENDING

    # Second call: Kafka recovers
    producer.send_and_wait.side_effect = None
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PROCESSED


# ---------------------------------------------------------------------------
# Verify: Commit is always called (atomicity)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kafka_commit_called_after_publish(mock_infra):
    """UoW commit is always called even when some events fail."""
    mock_uow, producer = mock_infra
    event = _make_event()
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = Exception("down")

    await outbox_publisher.publish_pending_events()
    mock_uow.commit.assert_called_once()
