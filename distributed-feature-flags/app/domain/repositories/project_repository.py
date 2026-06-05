import uuid
from abc import abstractmethod
from collections.abc import Sequence

from app.domain.repositories.base import Repository
from app.infrastructure.db.models import Project


class ProjectRepository(Repository[Project, uuid.UUID]):
    """Interface for Project persistence operations."""

    @abstractmethod
    async def get_by_name_and_org(
        self, name: str, organization_id: uuid.UUID
    ) -> Project | None:
        """Retrieve a project by name within a specific organization."""
        pass

    @abstractmethod
    async def list_for_org(self, organization_id: uuid.UUID) -> Sequence[Project]:
        """List all projects within a specific organization."""
        pass
