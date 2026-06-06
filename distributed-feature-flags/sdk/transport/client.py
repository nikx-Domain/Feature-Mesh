import asyncio
import logging
from typing import Any

import httpx

from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKNetworkException

logger = logging.getLogger(__name__)

class TransportClient:
    """
    Handles async HTTP communication with the Feature Flag backend.
    """

    def __init__(self, config: SDKConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "FeatureFlag-Python-SDK/2.0-Standalone"
            }
        )

    async def get_snapshot(self) -> dict[str, Any]:
        """
        Fetches the full environment snapshot with retries and exponential backoff.
        Handles temporary network failures and timeouts asynchronously.
        """
        # We simulate the api_key being the environment_id for easy demonstration.
        url = f"/environments/{self.config.api_key}/snapshot"
        
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response.json()
                
            except httpx.RequestError as e:
                logger.warning(f"Network error while fetching snapshot (attempt {attempt + 1}/{max_retries}): {e}")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} while fetching snapshot (attempt {attempt + 1}/{max_retries})")
                
            if attempt == max_retries - 1:
                raise SDKNetworkException(f"Failed to fetch snapshot after {max_retries} attempts")
            
            # Exponential backoff
            await asyncio.sleep(base_delay * (2 ** attempt))
                
        raise SDKNetworkException("Unexpected error during snapshot fetch")

    async def close(self):
        await self.client.aclose()
