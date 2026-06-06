import logging
from typing import Any

from sdk.cache.store import FlagStore
from sdk.config.config import SDKConfig
from sdk.evaluation.adapter import EvaluationEngineAdapter
from sdk.exceptions.exceptions import SDKInitializationException, SDKNetworkException
from sdk.models.dtos import SDKSnapshotDTO
from sdk.transport.client import TransportClient
from sdk.workers.refresh import RefreshManager

logger = logging.getLogger(__name__)


class FeatureFlagClient:
    """
    Main entrypoint for the Feature Flag SDK.
    Handles bootstrap, refresh lifecycle, and local evaluation.
    """

    def __init__(self, config: SDKConfig):
        self.config = config
        self.store = FlagStore()
        self.transport = TransportClient(config)
        self.refresh_manager = RefreshManager(config, self.store, self.transport)
        self._is_started = False

    def start(self) -> None:
        """
        Initializes the SDK by performing an initial bootstrap load of the flag cache,
        and then starts the background refresh thread.
        """
        if self._is_started:
            logger.warning("FeatureFlagClient is already started.")
            return

        if self.config.offline_mode:
            logger.info("Initializing in OFFLINE mode. No network calls will be made.")
            # In offline mode, the store remains empty unless populated manually.
        else:
            try:
                raw_snapshot = self.transport.get_snapshot()
                snapshot_dto = SDKSnapshotDTO(**raw_snapshot)
                self.store.update_snapshot(snapshot_dto)
                logger.info("Successfully bootstrapped local cache.")
            except Exception as e:
                logger.error(f"Failed to bootstrap cache: {e}")
                if self.config.bootstrap_mode == "fail_fast":
                    raise SDKInitializationException("Failed to bootstrap SDK") from e
                else:
                    logger.warning("Graceful bootstrap mode: continuing with empty cache. "
                                   "Will retry in background.")

            self.refresh_manager.start()

        self._is_started = True

    def close(self) -> None:
        """Stops background threads and cleans up."""
        self.refresh_manager.stop()
        self._is_started = False

    def is_enabled(self, flag_key: str, context: dict[str, Any] | None = None, default: bool = False) -> bool:
        """
        Evaluates a boolean feature flag against the given context.
        """
        context = context or {}
        
        if not self.store.is_initialized():
            logger.debug(f"SDK cache not initialized, returning default: {default} for {flag_key}")
            return default

        flag_dto = self.store.get_flag(flag_key)
        if not flag_dto:
            logger.debug(f"Flag {flag_key} not found in cache, returning default: {default}")
            return default

        try:
            decision = EvaluationEngineAdapter.evaluate(flag_dto, context)
            return decision.is_enabled
        except Exception as e:
            logger.error(f"Error evaluating flag {flag_key}: {e}")
            return default

    def get_variation(self, flag_key: str, context: dict[str, Any] | None = None, default: Any = None) -> Any:
        """
        Evaluates a multivariate feature flag against the given context and returns the variation value.
        """
        context = context or {}
        
        if not self.store.is_initialized():
            logger.debug(f"SDK cache not initialized, returning default: {default} for {flag_key}")
            return default

        flag_dto = self.store.get_flag(flag_key)
        if not flag_dto:
            logger.debug(f"Flag {flag_key} not found in cache, returning default: {default}")
            return default

        try:
            decision = EvaluationEngineAdapter.evaluate(flag_dto, context)
            return decision.variation_value if decision.variation_value is not None else default
        except Exception as e:
            logger.error(f"Error evaluating flag {flag_key}: {e}")
            return default
