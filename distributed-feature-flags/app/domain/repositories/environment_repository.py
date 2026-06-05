import uuid
from abc import abstractmethod
from collections.abc import Sequence

from app.domain.repositories.base import Repository
from app.infrastructure.db.models import Environment


class EnvironmentRepository(Repository[Environment, uuid.UUID]):
    """Interface for Environment persistence operations."""

    @abstractmethod
    async def get_by_name_and_project(
        self, name: str, project_id: uuid.UUID
    ) -> Environment | None:
        """Retrieve an environment by name within a specific project."""
        pass

    @abstractmethod
    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[Environment]:
        """List all environments within a specific project."""
        pass
