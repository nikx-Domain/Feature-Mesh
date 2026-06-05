import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    AuditEventEntity,
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
    RolloutRuleEntity,
    TargetingRuleEntity,
)
from app.domain.repositories.feature_flag_repository import (
    AuditEventRepository,
    FeatureFlagEnvironmentRepository,
    FeatureFlagRepository,
    FlagVariationRepository,
    RolloutRuleRepository,
    TargetingRuleRepository,
)
from app.infrastructure.db.models import (
    AuditEvent,
    FeatureFlag,
    FeatureFlagEnvironment,
    FlagVariation,
    RolloutRule,
    TargetingRule,
)


class SQLAlchemyFeatureFlagRepository(FeatureFlagRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: FeatureFlagEntity) -> None:
        model = FeatureFlag(**entity.model_dump())
        self.session.add(model)

    async def update(self, entity: FeatureFlagEntity) -> None:
        stmt = update(FeatureFlag).where(FeatureFlag.id == entity.id).values(**entity.model_dump(exclude={"id"}))
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> FeatureFlagEntity | None:
        model = await self.session.get(FeatureFlag, id)
        if model:
            return FeatureFlagEntity.model_validate(model)
        return None

    async def list_all(self) -> Sequence[FeatureFlagEntity]:
        result = await self.session.execute(select(FeatureFlag))
        return [FeatureFlagEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: FeatureFlagEntity) -> None:
        stmt = delete(FeatureFlag).where(FeatureFlag.id == entity.id)
        await self.session.execute(stmt)

    async def get_by_key_and_project(self, key: str, project_id: uuid.UUID) -> FeatureFlagEntity | None:
        stmt = select(FeatureFlag).where(
            FeatureFlag.key == key,
            FeatureFlag.project_id == project_id,
            FeatureFlag.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        model = result.scalars().first()
        return FeatureFlagEntity.model_validate(model) if model else None

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[FeatureFlagEntity]:
        stmt = select(FeatureFlag).where(
            FeatureFlag.project_id == project_id,
            FeatureFlag.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return [FeatureFlagEntity.model_validate(m) for m in result.scalars().all()]


class SQLAlchemyFlagVariationRepository(FlagVariationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: FlagVariationEntity) -> None:
        model = FlagVariation(**entity.model_dump())
        self.session.add(model)

    async def update(self, entity: FlagVariationEntity) -> None:
        stmt = update(FlagVariation).where(FlagVariation.id == entity.id).values(**entity.model_dump(exclude={"id"}))
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> FlagVariationEntity | None:
        model = await self.session.get(FlagVariation, id)
        return FlagVariationEntity.model_validate(model) if model else None

    async def list_all(self) -> Sequence[FlagVariationEntity]:
        result = await self.session.execute(select(FlagVariation))
        return [FlagVariationEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: FlagVariationEntity) -> None:
        stmt = delete(FlagVariation).where(FlagVariation.id == entity.id)
        await self.session.execute(stmt)

    async def list_for_flag(self, feature_flag_id: uuid.UUID) -> Sequence[FlagVariationEntity]:
        stmt = select(FlagVariation).where(FlagVariation.feature_flag_id == feature_flag_id)
        result = await self.session.execute(stmt)
        return [FlagVariationEntity.model_validate(m) for m in result.scalars().all()]


class SQLAlchemyFeatureFlagEnvironmentRepository(FeatureFlagEnvironmentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: FeatureFlagEnvironmentEntity) -> None:
        data = entity.model_dump(exclude={"targeting_rules", "rollout_rules"})
        model = FeatureFlagEnvironment(**data)
        self.session.add(model)

    async def update(self, entity: FeatureFlagEnvironmentEntity) -> None:
        data = entity.model_dump(exclude={"id", "targeting_rules", "rollout_rules"})
        stmt = update(FeatureFlagEnvironment).where(FeatureFlagEnvironment.id == entity.id).values(**data)
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> FeatureFlagEnvironmentEntity | None:
        model = await self.session.get(FeatureFlagEnvironment, id)
        return FeatureFlagEnvironmentEntity.model_validate(model) if model else None

    async def list_all(self) -> Sequence[FeatureFlagEnvironmentEntity]:
        result = await self.session.execute(select(FeatureFlagEnvironment))
        return [FeatureFlagEnvironmentEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: FeatureFlagEnvironmentEntity) -> None:
        stmt = delete(FeatureFlagEnvironment).where(FeatureFlagEnvironment.id == entity.id)
        await self.session.execute(stmt)

    async def get_by_flag_and_environment(
        self, feature_flag_id: uuid.UUID, environment_id: uuid.UUID
    ) -> FeatureFlagEnvironmentEntity | None:
        stmt = select(FeatureFlagEnvironment).where(
            FeatureFlagEnvironment.feature_flag_id == feature_flag_id,
            FeatureFlagEnvironment.environment_id == environment_id
        )
        result = await self.session.execute(stmt)
        model = result.scalars().first()
        return FeatureFlagEnvironmentEntity.model_validate(model) if model else None

    async def list_for_environment(self, environment_id: uuid.UUID) -> Sequence[FeatureFlagEnvironmentEntity]:
        stmt = select(FeatureFlagEnvironment).where(FeatureFlagEnvironment.environment_id == environment_id)
        result = await self.session.execute(stmt)
        return [FeatureFlagEnvironmentEntity.model_validate(m) for m in result.scalars().all()]


class SQLAlchemyTargetingRuleRepository(TargetingRuleRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: TargetingRuleEntity) -> None:
        model = TargetingRule(**entity.model_dump())
        self.session.add(model)

    async def update(self, entity: TargetingRuleEntity) -> None:
        stmt = update(TargetingRule).where(TargetingRule.id == entity.id).values(**entity.model_dump(exclude={"id"}))
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> TargetingRuleEntity | None:
        model = await self.session.get(TargetingRule, id)
        return TargetingRuleEntity.model_validate(model) if model else None

    async def list_all(self) -> Sequence[TargetingRuleEntity]:
        result = await self.session.execute(select(TargetingRule))
        return [TargetingRuleEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: TargetingRuleEntity) -> None:
        stmt = delete(TargetingRule).where(TargetingRule.id == entity.id)
        await self.session.execute(stmt)

    async def list_for_state(self, feature_flag_environment_id: uuid.UUID) -> Sequence[TargetingRuleEntity]:
        stmt = select(TargetingRule).where(
            TargetingRule.feature_flag_environment_id == feature_flag_environment_id
        ).order_by(TargetingRule.priority.asc())
        result = await self.session.execute(stmt)
        return [TargetingRuleEntity.model_validate(m) for m in result.scalars().all()]


class SQLAlchemyRolloutRuleRepository(RolloutRuleRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: RolloutRuleEntity) -> None:
        model = RolloutRule(**entity.model_dump())
        self.session.add(model)

    async def update(self, entity: RolloutRuleEntity) -> None:
        stmt = update(RolloutRule).where(RolloutRule.id == entity.id).values(**entity.model_dump(exclude={"id"}))
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> RolloutRuleEntity | None:
        model = await self.session.get(RolloutRule, id)
        return RolloutRuleEntity.model_validate(model) if model else None

    async def list_all(self) -> Sequence[RolloutRuleEntity]:
        result = await self.session.execute(select(RolloutRule))
        return [RolloutRuleEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: RolloutRuleEntity) -> None:
        stmt = delete(RolloutRule).where(RolloutRule.id == entity.id)
        await self.session.execute(stmt)

    async def list_for_state(self, feature_flag_environment_id: uuid.UUID) -> Sequence[RolloutRuleEntity]:
        stmt = select(RolloutRule).where(
            RolloutRule.feature_flag_environment_id == feature_flag_environment_id
        )
        result = await self.session.execute(stmt)
        return [RolloutRuleEntity.model_validate(m) for m in result.scalars().all()]


class SQLAlchemyAuditEventRepository(AuditEventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: AuditEventEntity) -> None:
        model = AuditEvent(**entity.model_dump())
        self.session.add(model)

    async def update(self, entity: AuditEventEntity) -> None:
        stmt = update(AuditEvent).where(AuditEvent.id == entity.id).values(**entity.model_dump(exclude={"id"}))
        await self.session.execute(stmt)

    async def get_by_id(self, id: uuid.UUID) -> AuditEventEntity | None:
        model = await self.session.get(AuditEvent, id)
        return AuditEventEntity.model_validate(model) if model else None

    async def list_all(self) -> Sequence[AuditEventEntity]:
        result = await self.session.execute(select(AuditEvent))
        return [AuditEventEntity.model_validate(m) for m in result.scalars().all()]

    async def delete(self, entity: AuditEventEntity) -> None:
        stmt = delete(AuditEvent).where(AuditEvent.id == entity.id)
        await self.session.execute(stmt)

    async def list_for_organization(self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> Sequence[AuditEventEntity]:
        stmt = select(AuditEvent).where(
            AuditEvent.organization_id == organization_id
        ).order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [AuditEventEntity.model_validate(m) for m in result.scalars().all()]

    async def list_for_entity(self, entity_id: uuid.UUID, entity_type: str) -> Sequence[AuditEventEntity]:
        stmt = select(AuditEvent).where(
            AuditEvent.entity_id == entity_id,
            AuditEvent.entity_type == entity_type
        ).order_by(AuditEvent.created_at.desc())
        result = await self.session.execute(stmt)
        return [AuditEventEntity.model_validate(m) for m in result.scalars().all()]
