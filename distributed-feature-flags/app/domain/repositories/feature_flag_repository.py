import uuid
from abc import abstractmethod
from collections.abc import Sequence

from app.domain.entities import (
    AuditEventEntity,
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
    RolloutRuleEntity,
    TargetingRuleEntity,
)
from app.domain.repositories.base import Repository


class FeatureFlagRepository(Repository[FeatureFlagEntity, uuid.UUID]):
    """Interface for Feature Flag persistence operations."""

    @abstractmethod
    async def get_by_key_and_project(
        self, key: str, project_id: uuid.UUID
    ) -> FeatureFlagEntity | None:
        """Retrieve a feature flag by its key within a project."""
        pass

    @abstractmethod
    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[FeatureFlagEntity]:
        """List all feature flags within a project."""
        pass


class FlagVariationRepository(Repository[FlagVariationEntity, uuid.UUID]):
    """Interface for Flag Variation persistence operations."""

    @abstractmethod
    async def list_for_flag(self, feature_flag_id: uuid.UUID) -> Sequence[FlagVariationEntity]:
        """List all variations for a feature flag."""
        pass


class FeatureFlagEnvironmentRepository(Repository[FeatureFlagEnvironmentEntity, uuid.UUID]):
    """Interface for Feature Flag Environment state persistence operations."""

    @abstractmethod
    async def get_by_flag_and_environment(
        self, feature_flag_id: uuid.UUID, environment_id: uuid.UUID
    ) -> FeatureFlagEnvironmentEntity | None:
        """Retrieve the state of a feature flag in a specific environment."""
        pass

    @abstractmethod
    async def list_for_environment(
        self, environment_id: uuid.UUID
    ) -> Sequence[FeatureFlagEnvironmentEntity]:
        """List all feature flag states within a specific environment."""
        pass


class TargetingRuleRepository(Repository[TargetingRuleEntity, uuid.UUID]):
    """Interface for Targeting Rule persistence operations."""

    @abstractmethod
    async def list_for_state(
        self, feature_flag_environment_id: uuid.UUID
    ) -> Sequence[TargetingRuleEntity]:
        """List all targeting rules for a specific flag state, ordered by priority."""
        pass


class RolloutRuleRepository(Repository[RolloutRuleEntity, uuid.UUID]):
    """Interface for Rollout Rule persistence operations."""

    @abstractmethod
    async def list_for_state(
        self, feature_flag_environment_id: uuid.UUID
    ) -> Sequence[RolloutRuleEntity]:
        """List all rollout rules for a specific flag state."""
        pass


class AuditEventRepository(Repository[AuditEventEntity, uuid.UUID]):
    """Interface for Audit Event persistence operations."""

    @abstractmethod
    async def list_for_organization(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> Sequence[AuditEventEntity]:
        """List audit events for an organization."""
        pass

    @abstractmethod
    async def list_for_entity(
        self, entity_id: uuid.UUID, entity_type: str
    ) -> Sequence[AuditEventEntity]:
        """List audit events for a specific entity (e.g. for Flag Versioning)."""
        pass
