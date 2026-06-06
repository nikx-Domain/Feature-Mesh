import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from sdk.client.client import FeatureFlagClient
from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKInitializationException, SDKNetworkException
from sdk.models.dtos import SDKSnapshotDTO


@pytest.fixture
def mock_snapshot_data():
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
                    "default_serve_variation_id": str(uuid.uuid4()),
                    "off_variation_id": str(uuid.uuid4()),
                    "targeting_rules": [],
                    "rollout_rules": []
                },
                "variations": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "true",
                        "value": True
                    },
                    {
                        "id": str(uuid.uuid4()),
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
    
    assert not client.store.is_initialized()
    assert client.is_enabled("some_flag", default=True) is True
    client.close()


@patch("sdk.transport.client.requests.Session.get")
def test_bootstrap_fail_fast(mock_get):
    mock_get.side_effect = Exception("Network error")
    
    config = SDKConfig(api_key="test", bootstrap_mode="fail_fast")
    client = FeatureFlagClient(config)
    
    with pytest.raises(SDKInitializationException):
        client.start()


@patch("sdk.transport.client.requests.Session.get")
def test_bootstrap_graceful(mock_get):
    mock_get.side_effect = Exception("Network error")
    
    config = SDKConfig(api_key="test", bootstrap_mode="graceful", refresh_interval=1)
    client = FeatureFlagClient(config)
    
    # Should not raise
    client.start()
    
    assert not client.store.is_initialized()
    assert client.is_enabled("some_flag", default=False) is False
    client.close()


@patch("sdk.transport.client.requests.Session.get")
def test_background_refresh(mock_get, mock_snapshot_data):
    mock_response = MagicMock()
    mock_response.json.return_value = mock_snapshot_data
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    config = SDKConfig(api_key="test", refresh_interval=1)
    client = FeatureFlagClient(config)
    
    client.start()
    
    assert client.store.is_initialized()
    
    # Simulate a new snapshot arriving
    new_snapshot_data = mock_snapshot_data.copy()
    new_snapshot_data["flags"]["test_flag"]["environment"]["is_enabled"] = False
    mock_response.json.return_value = new_snapshot_data
    
    # Wait for refresh thread to pick it up
    time.sleep(1.5)
    
    # Assert cache was swapped (adapter evaluation requires the real UUIDs to match, but since
    # our adapter just reads `is_enabled`, the mock data we built above is missing valid variation mappings for the adapter, 
    # but `is_enabled` will be checked first. Actually `is_enabled=False` uses `off_variation_id`.
    # Let's just assert the raw snapshot data was updated.
    flag = client.store.get_flag("test_flag")
    assert flag is not None
    assert flag.environment.is_enabled is False

    client.close()


def test_thread_safety():
    # Since GIL and assignment is atomic, we just verify the RLock doesn't deadlock
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
        
    client.close()
