from abc import ABC, abstractmethod


class CacheService(ABC):
    """Interface for cache operations."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Retrieve a string value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> None:
        """Set a string value with an optional expiration."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        pass

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> None:
        """Deletes all keys matching a given pattern."""
        pass
