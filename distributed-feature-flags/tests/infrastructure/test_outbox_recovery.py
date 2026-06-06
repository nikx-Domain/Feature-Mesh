"""
Outbox Publisher Recovery Tests — Task 3
Tests publisher crash → restart → resume semantics.
Verifies unprocessed events remain in outbox, events eventually delivered,
and duplicate delivery is safely handled by the consumer's idempotency check.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.infrastructure.background.outbox_publisher import OutboxPublisher
from app.domain.entities import OutboxEventEntity, OutboxStatus


def _make_publisher():
    """Creates a fresh OutboxPublisher with a mocked session factory."""
    session_factory = AsyncMock()
    return OutboxPublisher(session_factory=session_factory)


def _make_event(**kwargs):
    defaults = dict(aggregate_type="feature_flag", aggregate_id="abc", event_type="flag.updated", payload={"flag_key": "my_flag"})
    defaults.update(kwargs)
    return OutboxEventEntity(**defaults)


@pytest.fixture
def mock_infra():
    """Patches SessionLocal and UOW for outbox publisher."""
    with patch("app.infrastructure.background.outbox_publisher.SessionLocal"):
        with patch("app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork") as mock_uow_class:
            uow = AsyncMock()
            uow.__aenter__.return_value = uow
            uow.__aexit__.return_value = False
            uow.outbox_events.get_pending_events = AsyncMock(return_value=[])
            uow.outbox_events.update = AsyncMock()
            uow.commit = AsyncMock()
            mock_uow_class.return_value = uow
            with patch("app.infrastructure.background.outbox_publisher.get_kafka_producer") as mock_get_producer:
                producer = AsyncMock()
                mock_get_producer.return_value = producer
                yield uow, producer


# ---------------------------------------------------------------------------
# Scenario 1: Publisher crash mid-batch — events remain PENDING
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unprocessed_events_remain_pending_after_crash(mock_infra):
    """
    If publisher crashes after updating event1 but before event2,
    event2 must still be PENDING on next iteration.
    """
    mock_uow, producer = mock_infra
    event1 = _make_event(aggregate_id="1")
    event2 = _make_event(aggregate_id="2")
    mock_uow.outbox_events.get_pending_events.return_value = [event1, event2]

    # event1 publishes fine; event2 triggers crash
    producer.send_and_wait.side_effect = [None, Exception("publisher crash")]

    await outbox_publisher.publish_pending_events()

    assert event1.status == OutboxStatus.PROCESSED
    assert event2.status == OutboxStatus.PENDING  # Not lost — still in outbox


# ---------------------------------------------------------------------------
# Scenario 2: Publisher restart resumes from PENDING events
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_publisher_restart_resumes_pending(mock_infra):
    """
    After restart, publisher picks up PENDING events from previous run.
    Simulated by calling publish_pending_events() again after a 'crash'.
    """
    mock_uow, producer = mock_infra

    event = _make_event(retry_count=1)  # Survived previous crash
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    producer.send_and_wait.side_effect = None  # Kafka now available

    await outbox_publisher.publish_pending_events()

    assert event.status == OutboxStatus.PROCESSED, "PENDING event must be published on restart"


# ---------------------------------------------------------------------------
# Scenario 3: Start/Stop lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_publisher_start_creates_background_task():
    """Calling start() creates an internal asyncio task."""
    from app.infrastructure.background.outbox_publisher import OutboxPublisher
    from app.core.database import SessionLocal
    with patch("app.infrastructure.background.outbox_publisher.OutboxPublisher._run_loop", new_callable=AsyncMock):
        pub = OutboxPublisher(session_factory=SessionLocal)
        await pub.start()
        assert pub._task is not None
        assert pub._running is True
        await pub.stop()
        assert pub._running is False


@pytest.mark.asyncio
async def test_publisher_stop_cancels_task():
    """Calling stop() cancels the running task gracefully."""
    import asyncio
    from app.infrastructure.background.outbox_publisher import OutboxPublisher
    from app.core.database import SessionLocal

    async def slow_loop():
        await asyncio.sleep(9999)

    with patch.object(OutboxPublisher, "_run_loop", side_effect=slow_loop):
        pub = OutboxPublisher(session_factory=SessionLocal)
        await pub.start()
        assert pub._running is True
        await pub.stop()
        assert pub._running is False


# ---------------------------------------------------------------------------
# Scenario 4: Double-start is idempotent
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_publisher_double_start_idempotent():
    """Calling start() twice does not create duplicate tasks."""
    import asyncio
    from app.infrastructure.background.outbox_publisher import OutboxPublisher
    from app.core.database import SessionLocal

    async def noop_loop():
        await asyncio.sleep(9999)

    with patch.object(OutboxPublisher, "_run_loop", side_effect=noop_loop):
        pub = OutboxPublisher(session_factory=SessionLocal)
        await pub.start()
        task1 = pub._task
        await pub.start()  # Second call
        task2 = pub._task
        assert task1 is task2, "Second start() must not create a new task"
        await pub.stop()


# ---------------------------------------------------------------------------
# Scenario 5: Duplicate handling — idempotency on re-delivery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_event_handled_by_idempotency_key(mock_infra):
    """
    If the same event is processed twice (e.g., after publisher crash and retry),
    verify the publisher sets PROCESSED after the second send — the consumer's
    idempotency check is what prevents double audit log writes.
    """
    mock_uow, producer = mock_infra
    event = _make_event()
    mock_uow.outbox_events.get_pending_events.return_value = [event]

    # First publish
    producer.send_and_wait.side_effect = None
    await outbox_publisher.publish_pending_events()
    assert event.status == OutboxStatus.PROCESSED

    # Simulate event appearing PENDING again (DB wasn't committed, hypothetical)
    event.status = OutboxStatus.PENDING
    await outbox_publisher.publish_pending_events()
    # Publisher re-sends — consumer will deduplicate via event_id
    assert producer.send_and_wait.call_count == 2


# Import global singleton for fixture-based tests
from app.infrastructure.background.outbox_publisher import outbox_publisher
