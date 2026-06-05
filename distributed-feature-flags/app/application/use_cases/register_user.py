import uuid

from app.core.security import hash_password
from app.domain.exceptions import EntityAlreadyExistsException
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import User


class RegisterUserUseCase:
    """Use case to handle new user registrations via Unit of Work."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, email: str, password: str) -> User:
        async with self.uow:
            # Check for existing user
            existing_user = await self.uow.users.get_by_email(email)

            if existing_user:
                raise EntityAlreadyExistsException("User with this email already exists")

            # Hash credentials and persist user
            password_hash = hash_password(password)
            user = User(email=email, password_hash=password_hash, is_active=True)

            await self.uow.users.add(user)

            await self.uow.commit()
            return user
