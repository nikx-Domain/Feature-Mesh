import uuid

from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.security import hash_password
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import User
from app.infrastructure.repositories.base import SQLAlchemyRepository


class RegisterUserUseCase:
    """Use case to handle new user registrations via Unit of Work."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, email: str, password: str) -> User:
        async with self.uow:
            # Check for existing user
            stmt = select(User).where(User.email == email)
            result = await self.uow.session.execute(stmt)
            existing_user = result.scalars().first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email already exists",
                )

            # Hash credentials and persist user
            password_hash = hash_password(password)
            user = User(email=email, password_hash=password_hash, is_active=True)

            repo: SQLAlchemyRepository[User, uuid.UUID] = SQLAlchemyRepository(
                self.uow.session, User
            )
            await repo.add(user)

            await self.uow.commit()
            return user
