from abc import ABC, abstractmethod
from types import TracebackType

from app.domain.repositories.environment_repository import EnvironmentRepository
from app.domain.repositories.feature_flag_repository import (
    AuditEventRepository,
    FeatureFlagEnvironmentRepository,
    FeatureFlagRepository,
    FlagVariationRepository,
    RolloutRuleRepository,
    TargetingRuleRepository,
)
from app.domain.repositories.organization_repository import OrganizationRepository
from app.domain.repositories.project_repository import ProjectRepository
from app.domain.repositories.user_repository import UserRepository


class UnitOfWork(ABC):
    """Abstract generic Unit of Work (UOW) context manager interface."""

    @property
    @abstractmethod
    def users(self) -> UserRepository:
        pass

    @property
    @abstractmethod
    def organizations(self) -> OrganizationRepository:
        pass

    @property
    @abstractmethod
    def projects(self) -> ProjectRepository:
        pass

    @property
    @abstractmethod
    def environments(self) -> EnvironmentRepository:
        pass

    @property
    @abstractmethod
    def feature_flags(self) -> FeatureFlagRepository:
        pass

    @property
    @abstractmethod
    def flag_variations(self) -> FlagVariationRepository:
        pass

    @property
    @abstractmethod
    def feature_flag_environments(self) -> FeatureFlagEnvironmentRepository:
        pass

    @property
    @abstractmethod
    def targeting_rules(self) -> TargetingRuleRepository:
        pass

    @property
    @abstractmethod
    def rollout_rules(self) -> RolloutRuleRepository:
        pass

    @property
    @abstractmethod
    def audit_events(self) -> AuditEventRepository:
        pass

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.rollback()  # Default behavior if commit was not explicitly called

    @abstractmethod
    async def commit(self) -> None:
        """Commit the database transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the database transaction."""
        pass
