from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC, Generic[T, ID]):
    """Abstract generic repository interface defining standard read/write operations."""

    @abstractmethod
    async def add(self, entity: T) -> None:
        """Add an entity to the persistence context."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> None:
        """Update an existing entity in the persistence context."""
        pass

    @abstractmethod
    async def get_by_id(self, id: ID) -> T | None:
        """Retrieve an entity by its unique identifier."""
        pass

    @abstractmethod
    async def list_all(self) -> Sequence[T]:
        """Retrieve all active entities from persistence."""
        pass

    @abstractmethod
    async def delete(self, entity: T) -> None:
        """Remove an entity from persistence context."""
        pass
