import uuid

from app.domain.exceptions import EntityAlreadyExistsException
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Environment


class CreateEnvironmentUseCase:
    """Use case to handle creating environments in a project."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, project_id: uuid.UUID) -> Environment:
        async with self.uow:
            # Check environment name uniqueness within the same project
            existing_env = await self.uow.environments.get_by_name_and_project(name, project_id)

            if existing_env and existing_env.deleted_at is None:
                raise EntityAlreadyExistsException(
                    "Environment with this name already exists in the project"
                )

            env = Environment(name=name, project_id=project_id)
            await self.uow.environments.add(env)

            await self.uow.commit()
            return env
