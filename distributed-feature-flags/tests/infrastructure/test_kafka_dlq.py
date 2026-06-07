import pytest
import asyncio
from app.infrastructure.kafka.consumers.base import BaseConsumer
from aiokafka.structs import ConsumerRecord

class DummyConsumer(BaseConsumer):
    def __init__(self, group_id, topics):
        super().__init__(group_id, topics)
        self.process_calls = 0

    async def process_message(self, msg):
        self.process_calls += 1
        raise Exception("Simulated Failure")

pytestmark = pytest.mark.asyncio

async def test_dlq_fallback(mocker):
    consumer = DummyConsumer("test_group", ["test_topic"])
    
    mock_msg = ConsumerRecord(
        topic="test_topic", partition=0, offset=0, timestamp=0, timestamp_type=0,
        key=b"key", value=b"val", headers=[], checksum=0, serialized_key_size=3, serialized_value_size=3
    )
    
    mock_getone = mocker.patch("aiokafka.AIOKafkaConsumer.getone", return_value=mock_msg)
    mock_commit = mocker.patch("aiokafka.AIOKafkaConsumer.commit")
    
    # Mock send_kafka_message properly so it doesn't try to connect
    mock_send = mocker.patch("app.infrastructure.kafka.consumers.base.send_kafka_message")
    
    consumer._running = True
    consumer._consumer = mocker.MagicMock()
    consumer._consumer.getone = mock_getone
    consumer._consumer.commit = mock_commit
    
    # We run the loop for a short time
    async def stop_soon():
        await asyncio.sleep(0.5)
        consumer._running = False
    
    await asyncio.gather(consumer._run_loop(), stop_soon())
    
    # It should have tried to process it max_retries (3) times
    assert consumer.process_calls >= 3
    
    # And it should have published to DLQ
    mock_send.assert_called_with(
        topic="dead_letter_events",
        value=b"val",
        key=b"key",
        headers=[(b"original_topic", b"test_topic"), (b"group_id", b"test_group")]
    )
