import threading
from typing import Optional

from sdk.models.dtos import SDKSnapshotDTO, SDKFeatureFlagDTO


class FlagStore:
    """
    Thread-safe in-memory cache for Feature Flags.
    
    Data is replaced atomically by assigning a new reference to self._snapshot,
    so read operations only need to hold the lock briefly to get the reference,
    or we can rely on GIL for atomic assignments. However, we use an RLock
    to be explicit and completely safe across all Python implementations.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._snapshot: Optional[SDKSnapshotDTO] = None

    def update_snapshot(self, snapshot: SDKSnapshotDTO) -> None:
        """Atomically replaces the current snapshot with a new one."""
        with self._lock:
            self._snapshot = snapshot

    def get_flag(self, flag_key: str) -> Optional[SDKFeatureFlagDTO]:
        """Retrieves a specific flag by key."""
        with self._lock:
            if not self._snapshot:
                return None
            return self._snapshot.flags.get(flag_key)

    def is_initialized(self) -> bool:
        with self._lock:
            return self._snapshot is not None
