import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdk.client.client import FeatureFlagClient
from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKInitializationException, SDKNetworkException
from sdk.models.dtos import parse_snapshot


@pytest.fixture
def raw_snapshot_data():
    return {
        "environment_id": str(uuid.uuid4()),
        "flags": {
            "test_flag": {
                "id": str(uuid.uuid4()),
                "key": "test_flag",
                "type": "boolean",
                "version": 1,
                "environment": {
                    "is_enabled": True,
                    "default_serve_variation_id": "var-1",
                    "off_variation_id": "var-2",
                    "targeting_rules": [
                        {
                            "id": str(uuid.uuid4()),
                            "attribute": "country",
                            "operator": "equals",
                            "value": "IN",
                            "serve_variation_id": "var-1",
                            "priority": 0
                        }
                    ],
                    "rollout_rules": []
                },
                "variations": [
                    {
                        "id": "var-1",
                        "name": "true",
                        "value": True
                    },
                    {
                        "id": "var-2",
                        "name": "false",
                        "value": False
                    }
                ]
            }
        }
    }


def test_offline_mode():
    config = SDKConfig(api_key="test", offline_mode=True)
    client = FeatureFlagClient(config)
    client.start()
    
    assert client.health() == "offline"
    assert client.is_enabled("some_flag", default=True) is True
    client.shutdown()


@patch("sdk.transport.client.httpx.AsyncClient.get")
def test_bootstrap_fail_fast(mock_get):
    mock_get.side_effect = Exception("Network error")
    
    config = SDKConfig(api_key="test") # fail-fast is default behavior due to Exception raise
    client = FeatureFlagClient(config)
    
    with pytest.raises(SDKInitializationException):
        client.start()


@patch("sdk.transport.client.httpx.AsyncClient.get")
def test_background_refresh(mock_get, raw_snapshot_data):
    mock_response = AsyncMock()
    mock_response.json.return_value = raw_snapshot_data
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    config = SDKConfig(api_key="test", refresh_interval=1.0)
    client = FeatureFlagClient(config)
    
    # 1. Bootstrap
    client.start()
    assert client.health() == "healthy"
    assert client.is_enabled("test_flag") is True # Default serve variation is var-1 (True)
    
    # 2. Simulate background refresh
    new_data = raw_snapshot_data.copy()
    new_data["flags"]["test_flag"]["environment"]["is_enabled"] = False
    mock_response.json.return_value = new_data
    
    # Wait for the background refresh to occur
    time.sleep(1.5)
    
    assert client.is_enabled("test_flag") is False # Off variation is var-2 (False)
    client.shutdown()


def test_evaluation_engine_local_logic(raw_snapshot_data):
    # Test targeting rules locally
    config = SDKConfig(api_key="test", offline_mode=True)
    client = FeatureFlagClient(config)
    client.start()
    
    # Manually seed cache
    client.store.update_snapshot(parse_snapshot(raw_snapshot_data))
    
    # "country" == "IN" matches targeting rule -> var-1 (True)
    assert client.is_enabled("test_flag", context={"country": "IN"}) is True
    
    # "country" == "US" falls back to default serve -> var-1 (True)
    assert client.is_enabled("test_flag", context={"country": "US"}) is True
    client.shutdown()


def test_thread_safety():
    config = SDKConfig(api_key="test", offline_mode=True)
    client = FeatureFlagClient(config)
    client.start()

    def read_flags():
        for _ in range(100):
            client.is_enabled("test_flag")
            
    import threading
    threads = [threading.Thread(target=read_flags) for _ in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    client.shutdown()
