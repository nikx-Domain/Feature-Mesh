import uuid
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Project
from app.infrastructure.repositories.base import SQLAlchemyRepository
from fastapi import HTTPException, status
from sqlalchemy import select


class CreateProjectUseCase:
    """Use case to handle creating projects in an organization."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, organization_id: uuid.UUID) -> Project:
        async with self.uow:
            # Check project name uniqueness within the same organization
            stmt = select(Project).where(
                Project.organization_id == organization_id,
                Project.name == name,
                Project.deleted_at.is_(None),
            )
            result = await self.uow.session.execute(stmt)
            existing_project = result.scalars().first()

            if existing_project:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Project with this name already exists in the organization",
                )

            project = Project(name=name, organization_id=organization_id)
            repo: SQLAlchemyRepository[Project, uuid.UUID] = SQLAlchemyRepository(
                self.uow.session, Project
            )
            await repo.add(project)

            await self.uow.commit()
            return project
