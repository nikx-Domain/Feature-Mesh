from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.repositories.base import Repository

T = TypeVar("T")
ID = TypeVar("ID")


class SQLAlchemyRepository(Repository[T, ID], Generic[T, ID]):
    """Base SQLAlchemy Repository implementation for relational database persistence."""

    def __init__(self, session: AsyncSession, model_class: type[T]) -> None:
        self.session = session
        self.model_class = model_class

    async def add(self, entity: T) -> None:
        self.session.add(entity)

    async def update(self, entity: T) -> None:
        # For pure SQLAlchemy models, the session tracks changes automatically.
        # This method is mostly for explicitly merging or when using pure domain entities.
        pass

    async def get_by_id(self, id: ID) -> T | None:
        return await self.session.get(self.model_class, id)

    async def list_all(self) -> Sequence[T]:
        result = await self.session.execute(select(self.model_class))
        return result.scalars().all()

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
