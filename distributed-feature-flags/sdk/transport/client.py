import logging
import time
from typing import Any, Optional

import requests

from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKNetworkException

logger = logging.getLogger(__name__)


class TransportClient:
    """
    Handles HTTP communication with the Feature Flag backend.
    """

    def __init__(self, config: SDKConfig):
        self.config = config
        # The base URL should include the api path up to environments if standard,
        # but the backend route is just /environments/{environment_id}/snapshot
        # Let's assume the base_url is the root of the API, e.g. http://localhost:8000/api/v1
        # The environment_id is actually the api_key in this simple simulated SDK design.
        # So we fetch /api/v1/environments/{api_key}/snapshot
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config.api_key}",
            "User-Agent": "FeatureFlag-Python-SDK/1.0"
        })

    def get_snapshot(self) -> dict[str, Any]:
        """
        Fetches the full environment snapshot with retries and exponential backoff.
        Handles temporary network failures and timeouts.
        """
        url = f"{self.config.base_url}/environments/{self.config.api_key}/snapshot"
        
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to fetch snapshot (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt == max_retries - 1:
                    raise SDKNetworkException(f"Failed to fetch snapshot after {max_retries} attempts") from e
                
                # Exponential backoff
                time.sleep(base_delay * (2 ** attempt))
                
        raise SDKNetworkException("Unexpected error during snapshot fetch")
