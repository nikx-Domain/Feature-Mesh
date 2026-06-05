from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.environment_repository import EnvironmentRepository
from app.domain.repositories.organization_repository import OrganizationRepository
from app.domain.repositories.project_repository import ProjectRepository
from app.domain.repositories.user_repository import UserRepository
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.repositories.environment_repository import (
    SQLAlchemyEnvironmentRepository,
)
from app.infrastructure.repositories.outbox_repository import SQLAlchemyOutboxEventRepository
from app.infrastructure.repositories.feature_flag_repository import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyFeatureFlagEnvironmentRepository,
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyFlagVariationRepository,
    SQLAlchemyRolloutRuleRepository,
    SQLAlchemyTargetingRuleRepository,
)
from app.infrastructure.repositories.organization_repository import (
    SQLAlchemyOrganizationRepository,
)
from app.infrastructure.repositories.project_repository import (
    SQLAlchemyProjectRepository,
)
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


class SQLAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of the Unit of Work (UOW) context manager."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = SQLAlchemyUserRepository(session)
        self._organizations = SQLAlchemyOrganizationRepository(session)
        self._projects = SQLAlchemyProjectRepository(session)
        self._environments = SQLAlchemyEnvironmentRepository(session)
        self._feature_flags = SQLAlchemyFeatureFlagRepository(session)
        self._flag_variations = SQLAlchemyFlagVariationRepository(session)
        self._feature_flag_environments = SQLAlchemyFeatureFlagEnvironmentRepository(session)
        self._targeting_rules = SQLAlchemyTargetingRuleRepository(session)
        self._rollout_rules = SQLAlchemyRolloutRuleRepository(session)
        self._audit_events = SQLAlchemyAuditEventRepository(session)
        self._outbox_events = SQLAlchemyOutboxEventRepository(session)

    @property
    def users(self) -> UserRepository:
        return self._users

    @property
    def organizations(self) -> OrganizationRepository:
        return self._organizations

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    @property
    def environments(self) -> EnvironmentRepository:
        return self._environments

    @property
    def feature_flags(self):
        return self._feature_flags

    @property
    def flag_variations(self):
        return self._flag_variations

    @property
    def feature_flag_environments(self):
        return self._feature_flag_environments

    @property
    def targeting_rules(self):
        return self._targeting_rules

    @property
    def rollout_rules(self):
        return self._rollout_rules

    @property
    def audit_events(self):
        return self._audit_events

    @property
    def outbox_events(self):
        return self._outbox_events


    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
            else:
                # Default safety behavior: rollback if not explicitly committed
                await self.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
