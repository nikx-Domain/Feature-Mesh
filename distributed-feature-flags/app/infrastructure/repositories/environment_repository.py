import uuid
from collections.abc import Sequence

from sqlalchemy.future import select

from app.domain.repositories.environment_repository import EnvironmentRepository
from app.infrastructure.db.models import Environment
from app.infrastructure.repositories.base import SQLAlchemyRepository


class SQLAlchemyEnvironmentRepository(
    SQLAlchemyRepository[Environment, uuid.UUID], EnvironmentRepository
):
    """SQLAlchemy implementation of the EnvironmentRepository interface."""

    def __init__(self, session) -> None:
        super().__init__(session, Environment)

    async def get_by_name_and_project(
        self, name: str, project_id: uuid.UUID
    ) -> Environment | None:
        stmt = select(Environment).where(
            Environment.name == name, Environment.project_id == project_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[Environment]:
        stmt = select(Environment).where(Environment.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
