import uuid

from app.domain.repositories.base import Repository
from app.infrastructure.db.models import User


class UserRepository(Repository[User, uuid.UUID]):
    """Interface for User persistence operations."""

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address."""
        pass
