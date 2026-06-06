import pytest
from jsonschema import validate, ValidationError

# Kafka Event Schema Definitions
BASE_EVENT_SCHEMA = {
    "type": "object",
    "required": ["event_id", "event_type", "timestamp", "payload"],
    "properties": {
        "event_id": {"type": "string", "format": "uuid"},
        "event_type": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "payload": {"type": "object"}
    }
}

FLAG_CREATED_PAYLOAD = {
    "type": "object",
    "required": ["flag_id", "key", "name", "project_id"],
    "properties": {
        "flag_id": {"type": "string", "format": "uuid"},
        "key": {"type": "string"},
        "name": {"type": "string"},
        "project_id": {"type": "string", "format": "uuid"}
    }
}

def test_flag_created_event_schema_valid():
    valid_event = {
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "event_type": "flag.created",
        "timestamp": "2023-10-01T12:00:00Z",
        "payload": {
            "flag_id": "123e4567-e89b-12d3-a456-426614174001",
            "key": "new_checkout",
            "name": "New Checkout",
            "project_id": "123e4567-e89b-12d3-a456-426614174002"
        }
    }
    # Validate base
    validate(instance=valid_event, schema=BASE_EVENT_SCHEMA)
    # Validate specific payload
    validate(instance=valid_event["payload"], schema=FLAG_CREATED_PAYLOAD)

def test_flag_created_event_schema_invalid():
    invalid_event = {
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "event_type": "flag.created",
        "timestamp": "2023-10-01T12:00:00Z",
        "payload": {
            "flag_id": "123e4567-e89b-12d3-a456-426614174001",
            "key": "new_checkout",
            # missing name and project_id
        }
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_event["payload"], schema=FLAG_CREATED_PAYLOAD)
