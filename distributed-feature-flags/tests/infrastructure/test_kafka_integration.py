import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.domain.entities import OutboxEventEntity, OutboxStatus

@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    uow.outbox_events.get_pending_events = AsyncMock(return_value=[])
    uow.outbox_events.update = AsyncMock()
    uow.commit = AsyncMock()
    
    return uow

@pytest.fixture
def mock_session_local(mock_uow):
    with patch('app.infrastructure.background.outbox_publisher.SessionLocal') as session_local:
        session = AsyncMock()
        session_local.return_value = session
        with patch('app.infrastructure.background.outbox_publisher.SQLAlchemyUnitOfWork') as mock_uow_class:
            mock_uow_class.return_value = mock_uow
            yield mock_uow_class

@pytest.fixture
def mock_kafka_producer():
    with patch('app.infrastructure.background.outbox_publisher.get_kafka_producer') as mock_get_producer:
        producer = AsyncMock()
        mock_get_producer.return_value = producer
        yield producer

@pytest.mark.asyncio
async def test_outbox_publisher_no_events(mock_uow, mock_session_local, mock_kafka_producer):
    # Setup mock to return no events
    mock_uow.outbox_events.get_pending_events.return_value = []
    
    # Run a single iteration of the inner loop by mocking the outer loop condition
    with patch('app.infrastructure.background.outbox_publisher.asyncio.sleep', AsyncMock(side_effect=Exception("Stop Loop"))):
        try:
            await outbox_publisher.publish_pending_events()
        except Exception as e:
            assert str(e) == "Stop Loop"
            
    mock_kafka_producer.send_and_wait.assert_not_called()

@pytest.mark.asyncio
async def test_outbox_publisher_with_events(mock_uow, mock_session_local, mock_kafka_producer):
    event = OutboxEventEntity(aggregate_type="test", aggregate_id="123", event_type="flag-events", payload={"test": "data"})
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    
    with patch('app.infrastructure.background.outbox_publisher.asyncio.sleep', AsyncMock(side_effect=Exception("Stop Loop"))):
        try:
            await outbox_publisher.publish_pending_events()
        except Exception as e:
            assert str(e) == "Stop Loop"
            
    mock_kafka_producer.send_and_wait.assert_called_once()
    assert event.status == OutboxStatus.PROCESSED
    mock_uow.outbox_events.update.assert_called_once_with(event)
    mock_uow.commit.assert_called()

@pytest.mark.asyncio
async def test_outbox_publisher_kafka_failure_retry(mock_uow, mock_session_local, mock_kafka_producer):
    event = OutboxEventEntity(aggregate_type="test", aggregate_id="123", event_type="flag-events", payload={"test": "data"}, retry_count=0)
    mock_uow.outbox_events.get_pending_events.return_value = [event]
    
    # Simulate Kafka Outage
    mock_kafka_producer.send_and_wait.side_effect = Exception("Kafka down")
    
    with patch('app.infrastructure.background.outbox_publisher.asyncio.sleep', AsyncMock(side_effect=Exception("Stop Loop"))):
        try:
            await outbox_publisher.publish_pending_events()
        except Exception as e:
            assert str(e) == "Stop Loop"
            
    # Event should be marked as FAILED if retry_count > 5, but it's 0 so it just increments
    assert event.retry_count == 1
    assert event.status == OutboxStatus.PENDING # Remains pending for retry
    mock_uow.outbox_events.update.assert_called_once_with(event)
