import pytest
import json
from unittest.mock import AsyncMock
from aiokafka.structs import ConsumerRecord
from app.infrastructure.kafka.consumers.cache_consumer import CacheInvalidationConsumer

@pytest.fixture
def mock_cache_service():
    return AsyncMock()

@pytest.fixture
def consumer(mock_cache_service):
    return CacheInvalidationConsumer(mock_cache_service)

@pytest.mark.asyncio
async def test_process_message_missing_headers(consumer):
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=b'{"test": "data"}', headers=[], checksum=0, serialized_key_size=0, serialized_value_size=0)
    await consumer.process_message(msg)
    consumer.cache_service.delete_pattern.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_invalid_json(consumer):
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=b'invalid', headers=[("event_type", b"flag.updated"), ("event_id", b"1")], checksum=0, serialized_key_size=0, serialized_value_size=0)
    await consumer.process_message(msg)
    consumer.cache_service.delete_pattern.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_missing_flag_key(consumer):
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=b'{}', headers=[("event_type", b"flag.updated"), ("event_id", b"1")], checksum=0, serialized_key_size=0, serialized_value_size=0)
    await consumer.process_message(msg)
    consumer.cache_service.delete_pattern.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_flag_updated(consumer):
    val = json.dumps({"flag_key": "test"}).encode("utf-8")
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=val, headers=[("event_type", b"flag.updated"), ("event_id", b"1")], checksum=0, serialized_key_size=0, serialized_value_size=0)
    await consumer.process_message(msg)
    consumer.cache_service.delete_pattern.assert_any_call("eval_ptr:*:test")
    consumer.cache_service.delete_pattern.assert_any_call("eval_data:*:test:*")

@pytest.mark.asyncio
async def test_process_message_flag_toggled(consumer):
    val = json.dumps({"flag_key": "test", "environment_id": "env1"}).encode("utf-8")
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=val, headers=[("event_type", b"flag.toggled"), ("event_id", b"1")], checksum=0, serialized_key_size=0, serialized_value_size=0)
    await consumer.process_message(msg)
    consumer.cache_service.delete.assert_called_once_with("eval_ptr:env1:test")
    consumer.cache_service.delete_pattern.assert_called_once_with("eval_data:env1:test:*")

@pytest.mark.asyncio
async def test_process_message_exception(consumer):
    val = json.dumps({"flag_key": "test"}).encode("utf-8")
    msg = ConsumerRecord(topic="flag-events", partition=0, offset=1, timestamp=1, timestamp_type=0, key=None, value=val, headers=[("event_type", b"flag.updated"), ("event_id", b"1")], checksum=0, serialized_key_size=0, serialized_value_size=0)
    consumer.cache_service.delete_pattern.side_effect = Exception("error")
    with pytest.raises(Exception):
        await consumer.process_message(msg)
