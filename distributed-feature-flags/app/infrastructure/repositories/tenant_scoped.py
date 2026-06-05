import uuid
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.repositories.base import Repository

T = TypeVar("T")
ID = TypeVar("ID")


class TenantScopedRepository(Repository[T, ID], Generic[T, ID]):
    """
    Base repository for models that are strictly scoped to an organization (Tenant).
    Ensures that all read operations implicitly filter by the active tenant ID.
    """

    def __init__(
        self, session: AsyncSession, model_class: type[T], organization_id: uuid.UUID
    ) -> None:
        self.session = session
        self.model_class = model_class
        self.organization_id = organization_id

    def _get_base_stmt(self):
        # Assuming the model has an `organization_id` attribute
        return select(self.model_class).where(
            self.model_class.organization_id == self.organization_id  # type: ignore
        )

    async def add(self, entity: T) -> None:
        # Enforce tenant scope on the entity being added
        if hasattr(entity, "organization_id"):
            setattr(entity, "organization_id", self.organization_id)
        self.session.add(entity)

    async def get_by_id(self, id: ID) -> T | None:
        stmt = self._get_base_stmt().where(self.model_class.id == id)  # type: ignore
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_all(self) -> list[T]:
        stmt = self._get_base_stmt()
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
