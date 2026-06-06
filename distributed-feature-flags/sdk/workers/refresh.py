import logging
import threading
import time

from sdk.cache.store import FlagStore
from sdk.config.config import SDKConfig
from sdk.exceptions.exceptions import SDKNetworkException
from sdk.models.dtos import SDKSnapshotDTO
from sdk.transport.client import TransportClient

logger = logging.getLogger(__name__)


class RefreshManager:
    """
    Runs a background daemon thread to periodically fetch the latest
    flag snapshot and update the in-memory cache.
    """

    def __init__(self, config: SDKConfig, store: FlagStore, transport: TransportClient):
        self.config = config
        self.store = store
        self.transport = transport
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="FeatureFlagRefreshThread")

    def start(self):
        """Starts the background refresh thread."""
        if self.config.offline_mode:
            logger.info("SDK is in offline mode. Background refresh is disabled.")
            return

        if not self._thread.is_alive():
            self._stop_event.clear()
            self._thread.start()

    def stop(self):
        """Signals the background thread to stop and waits for it to finish."""
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self):
        """The main loop for the refresh thread."""
        logger.info(f"Background refresh started. Polling every {self.config.refresh_interval} seconds.")
        while not self._stop_event.is_set():
            # Wait for the interval, but allow interruption if stopped
            if self._stop_event.wait(self.config.refresh_interval):
                break

            try:
                raw_snapshot = self.transport.get_snapshot()
                snapshot_dto = SDKSnapshotDTO(**raw_snapshot)
                
                # Atomic replacement in store
                self.store.update_snapshot(snapshot_dto)
                logger.debug("Successfully refreshed local cache.")
            except SDKNetworkException as e:
                logger.error(f"Background refresh failed due to network error: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error during background refresh: {e}")
