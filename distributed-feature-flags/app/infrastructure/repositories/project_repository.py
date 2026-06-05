import uuid
from collections.abc import Sequence

from sqlalchemy.future import select

from app.domain.repositories.project_repository import ProjectRepository
from app.infrastructure.db.models import Project
from app.infrastructure.repositories.base import SQLAlchemyRepository


class SQLAlchemyProjectRepository(
    SQLAlchemyRepository[Project, uuid.UUID], ProjectRepository
):
    """SQLAlchemy implementation of the ProjectRepository interface."""

    def __init__(self, session) -> None:
        super().__init__(session, Project)

    async def get_by_name_and_org(
        self, name: str, organization_id: uuid.UUID
    ) -> Project | None:
        stmt = select(Project).where(
            Project.name == name, Project.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_org(self, organization_id: uuid.UUID) -> Sequence[Project]:
        stmt = select(Project).where(Project.organization_id == organization_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
