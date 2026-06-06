from typing import Optional

from sdk.models.dtos import SDKSnapshot, SDKFeatureFlag

class FlagStore:
    """
    In-memory cache for Feature Flags.
    
    Reads are completely lock-free. In Python, reference assignment 
    (e.g., self._snapshot = new_snapshot) is atomic under the GIL.
    Therefore, updating the snapshot simply involves replacing the reference,
    and any concurrent reads will either get the old complete snapshot or 
    the new complete snapshot, without any partial state corruption.
    """
    def __init__(self):
        self._snapshot: Optional[SDKSnapshot] = None

    def update_snapshot(self, snapshot: SDKSnapshot) -> None:
        """Atomically replaces the entire snapshot cache."""
        self._snapshot = snapshot

    def get_flag(self, flag_key: str) -> Optional[SDKFeatureFlag]:
        """Lock-free read of a feature flag."""
        # Grab a local reference to the snapshot safely
        snapshot = self._snapshot
        if not snapshot:
            return None
        return snapshot.flags.get(flag_key)

    def is_initialized(self) -> bool:
        """Lock-free check if the cache is seeded."""
        return self._snapshot is not None
