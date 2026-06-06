import asyncio
import logging
from typing import Any, Dict, Optional

from sdk.cache.store import FlagStore
from sdk.config.config import SDKConfig
from sdk.evaluation.engine import LocalEvaluationEngine
from sdk.exceptions.exceptions import SDKInitializationException
from sdk.models.dtos import parse_snapshot
from sdk.refresh.manager import RefreshManager
from sdk.transport.client import TransportClient

logger = logging.getLogger(__name__)

class FeatureFlagClient:
    """
    Main entrypoint for the Standalone Feature Flag SDK.
    """

    def __init__(self, config: SDKConfig):
        self.config = config
        self.store = FlagStore()
        self.refresh_manager = RefreshManager(self.config, self.store)
        self._is_started = False

    def start(self) -> None:
        """
        Initializes the SDK. If offline_mode is False, performs a synchronous-blocking 
        fetch for the initial snapshot to guarantee safety on startup.
        """
        if self._is_started:
            return

        if self.config.offline_mode:
            logger.info("Initializing in OFFLINE mode.")
        else:
            # We perform a one-time async fetch in the main thread's local event loop 
            # to block startup until we get the first snapshot.
            try:
                raw_snapshot = asyncio.run(self._bootstrap_fetch())
                snapshot = parse_snapshot(raw_snapshot)
                self.store.update_snapshot(snapshot)
                logger.info("Successfully bootstrapped local cache.")
            except Exception as e:
                logger.error(f"Bootstrap failed: {e}")
                # "fail-fast mode"
                raise SDKInitializationException("Failed to bootstrap SDK") from e

            # Start background refresh
            self.refresh_manager.start()

        self._is_started = True

    async def _bootstrap_fetch(self):
        transport = TransportClient(self.config)
        try:
            return await transport.get_snapshot()
        finally:
            await transport.close()

    def shutdown(self) -> None:
        """Gracefully stops background processes."""
        self.refresh_manager.stop()
        self._is_started = False

    def is_enabled(self, flag_key: str, context: Optional[Dict[str, Any]] = None, default: bool = False) -> bool:
        """Evaluates a flag purely locally without HTTP requests."""
        context = context or {}
        
        if not self.store.is_initialized():
            return default

        flag = self.store.get_flag(flag_key)
        if not flag:
            return default

        try:
            decision = LocalEvaluationEngine.evaluate(flag, context)
            if self.config.metrics_reporter:
                self.config.metrics_reporter.increment("sdk_evaluations_total", {"flag_key": flag_key})
            return decision.is_enabled
        except Exception as e:
            logger.error(f"Error evaluating flag {flag_key}: {e}")
            return default

    def get_variation(self, flag_key: str, context: Optional[Dict[str, Any]] = None, default: Any = None) -> Any:
        """Evaluates a multivariate flag purely locally."""
        context = context or {}
        
        if not self.store.is_initialized():
            return default

        flag = self.store.get_flag(flag_key)
        if not flag:
            return default

        try:
            decision = LocalEvaluationEngine.evaluate(flag, context)
            if self.config.metrics_reporter:
                self.config.metrics_reporter.increment("sdk_evaluations_total", {"flag_key": flag_key})
            return decision.variation_value if decision.variation_value is not None else default
        except Exception as e:
            logger.error(f"Error evaluating flag {flag_key}: {e}")
            return default

    def refresh(self) -> None:
        """Forces an immediate refresh of the snapshot."""
        self.refresh_manager.force_refresh()

    def health(self) -> str:
        """Returns the SDK operational status."""
        if not self._is_started:
            return "stopped"
        if self.config.offline_mode:
            return "offline"
        if self.store.is_initialized():
            return "healthy"
        return "uninitialized"
