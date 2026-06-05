from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any


class UnitOfWork(ABC):
    """Abstract generic Unit of Work (UOW) context manager interface."""

    @property
    @abstractmethod
    def session(self) -> Any:
        """Provide access to the underlying persistence session/context."""
        pass

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.rollback()  # Default behavior if commit was not explicitly called

    @abstractmethod
    async def commit(self) -> None:
        """Commit the database transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the database transaction."""
        pass
