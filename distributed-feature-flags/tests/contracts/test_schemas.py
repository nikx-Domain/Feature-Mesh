import pytest
from jsonschema import validate, ValidationError

# SDK Snapshot Schema Definition
SDK_SNAPSHOT_SCHEMA = {
    "type": "object",
    "required": ["environment_id", "flags"],
    "properties": {
        "environment_id": {"type": "string", "format": "uuid"},
        "flags": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["id", "key", "type", "version", "environment", "variations"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "key": {"type": "string"},
                    "type": {"type": "string"},
                    "version": {"type": "integer"},
                    "environment": {
                        "type": "object",
                        "required": ["is_enabled", "default_serve_variation_id", "off_variation_id", "targeting_rules", "rollout_rules"]
                    },
                    "variations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "name", "value"]
                        }
                    }
                }
            }
        }
    }
}

def test_sdk_snapshot_schema_valid():
    valid_payload = {
        "environment_id": "123e4567-e89b-12d3-a456-426614174000",
        "flags": {
            "my_flag": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "key": "my_flag",
                "type": "boolean",
                "version": 2,
                "environment": {
                    "is_enabled": True,
                    "default_serve_variation_id": "var1",
                    "off_variation_id": "var2",
                    "targeting_rules": [],
                    "rollout_rules": []
                },
                "variations": [
                    {"id": "var1", "name": "true", "value": True},
                    {"id": "var2", "name": "false", "value": False}
                ]
            }
        }
    }
    validate(instance=valid_payload, schema=SDK_SNAPSHOT_SCHEMA)

def test_sdk_snapshot_schema_invalid():
    invalid_payload = {
        "environment_id": "123e4567-e89b-12d3-a456-426614174000",
        # Missing 'flags'
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_payload, schema=SDK_SNAPSHOT_SCHEMA)
