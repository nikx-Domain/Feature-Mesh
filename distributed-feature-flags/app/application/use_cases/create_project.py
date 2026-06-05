import uuid

from app.domain.exceptions import EntityAlreadyExistsException
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Project


class CreateProjectUseCase:
    """Use case to handle creating projects in an organization."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, organization_id: uuid.UUID) -> Project:
        async with self.uow:
            # Check project name uniqueness within the same organization
            existing_project = await self.uow.projects.get_by_name_and_org(name, organization_id)

            if existing_project and existing_project.deleted_at is None:
                raise EntityAlreadyExistsException(
                    "Project with this name already exists in the organization"
                )

            project = Project(name=name, organization_id=organization_id)
            await self.uow.projects.add(project)

            await self.uow.commit()
            return project
