import asyncio
import logging
import threading

from sdk.cache.store import FlagStore
from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKNetworkException
from sdk.models.dtos import parse_snapshot
from sdk.transport.client import TransportClient

logger = logging.getLogger(__name__)

class RefreshManager:
    """
    Manages an asyncio event loop running in a background daemon thread.
    Periodically fetches the latest snapshot and performs atomic cache replacements.
    """
    def __init__(self, config: SDKConfig, store: FlagStore):
        self.config = config
        self.store = store
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SDKRefreshThread")
        self._loop = None
        self._transport = None

    def start(self):
        if self.config.offline_mode:
            logger.info("SDK is in offline mode. Background refresh is disabled.")
            return

        if not self._thread.is_alive():
            self._stop_event.clear()
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def force_refresh(self) -> None:
        """Synchronously blocks until a refresh is completed via the background loop."""
        if not self._loop or self.config.offline_mode:
            return
            
        future = asyncio.run_coroutine_threadsafe(self._do_refresh(), self._loop)
        try:
            future.result(timeout=self.config.timeout)
        except Exception as e:
            logger.error(f"Force refresh failed: {e}")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._transport = TransportClient(self.config)
        
        try:
            self._loop.run_until_complete(self._refresh_loop())
        finally:
            self._loop.run_until_complete(self._transport.close())
            self._loop.close()

    async def _refresh_loop(self):
        logger.info(f"Background refresh started. Polling every {self.config.refresh_interval}s.")
        while not self._stop_event.is_set():
            # Wait for interval or stop event
            # We check in small increments to be responsive to shutdown
            for _ in range(int(self.config.refresh_interval * 10)):
                if self._stop_event.is_set():
                    return
                await asyncio.sleep(0.1)

            await self._do_refresh()

    async def _do_refresh(self):
        if not self._transport:
            return
            
        try:
            raw_data = await self._transport.get_snapshot()
            snapshot = parse_snapshot(raw_data)
            self.store.update_snapshot(snapshot)
            logger.debug("Successfully refreshed local cache via background thread.")
            
            if self.config.metrics_reporter:
                self.config.metrics_reporter.increment("sdk_snapshot_refresh_total", {"status": "success"})
                self.config.metrics_reporter.increment("sdk_cache_replacements_total")
                
        except SDKNetworkException as e:
            if self.config.metrics_reporter:
                self.config.metrics_reporter.increment("sdk_snapshot_refresh_total", {"status": "error"})
                self.config.metrics_reporter.increment("sdk_snapshot_refresh_failures_total")
            logger.error(f"Background refresh failed (network): {e}")
        except Exception as e:
            if self.config.metrics_reporter:
                self.config.metrics_reporter.increment("sdk_snapshot_refresh_total", {"status": "error"})
                self.config.metrics_reporter.increment("sdk_snapshot_refresh_failures_total")
            logger.exception(f"Unexpected error during background refresh: {e}")
