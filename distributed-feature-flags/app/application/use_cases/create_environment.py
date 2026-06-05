import uuid
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Environment
from app.infrastructure.repositories.base import SQLAlchemyRepository
from fastapi import HTTPException, status
from sqlalchemy import select


class CreateEnvironmentUseCase:
    """Use case to handle creating environments in a project."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, project_id: uuid.UUID) -> Environment:
        async with self.uow:
            # Check environment name uniqueness within the same project
            stmt = select(Environment).where(
                Environment.project_id == project_id,
                Environment.name == name,
                Environment.deleted_at.is_(None),
            )
            result = await self.uow.session.execute(stmt)
            existing_env = result.scalars().first()

            if existing_env:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Environment with this name already exists in the project",
                )

            env = Environment(name=name, project_id=project_id)
            repo: SQLAlchemyRepository[Environment, uuid.UUID] = SQLAlchemyRepository(
                self.uow.session, Environment
            )
            await repo.add(env)

            await self.uow.commit()
            return env
