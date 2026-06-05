import uuid
from abc import abstractmethod
from collections.abc import Sequence

from app.domain.repositories.base import Repository
from app.infrastructure.db.models import Organization, UserOrganization


class OrganizationRepository(Repository[Organization, uuid.UUID]):
    """Interface for Organization persistence operations."""

    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Organization]:
        """Retrieve all organizations that a user belongs to."""
        pass

    @abstractmethod
    async def get_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> UserOrganization | None:
        """Retrieve the membership record linking a user to an organization."""
        pass

    @abstractmethod
    async def add_membership(self, membership: UserOrganization) -> None:
        """Add a user to an organization."""
        pass
