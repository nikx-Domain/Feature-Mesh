import uuid

from sqlalchemy.future import select

from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.db.models import User
from app.infrastructure.repositories.base import SQLAlchemyRepository


class SQLAlchemyUserRepository(SQLAlchemyRepository[User, uuid.UUID], UserRepository):
    """SQLAlchemy implementation of the UserRepository interface."""

    def __init__(self, session) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()
