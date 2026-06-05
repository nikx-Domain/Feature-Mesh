import uuid

from app.domain.entities import (
    ActionType,
    AuditEventEntity,
    EntityType,
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagType,
    FlagVariationEntity,
)
from app.domain.exceptions import EntityAlreadyExistsException
from app.domain.unit_of_work import UnitOfWork


class CreateFeatureFlagUseCase:
    """Use case to handle creating feature flags."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        name: str,
        key: str,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        description: str | None = None,
        flag_type: FlagType = FlagType.BOOLEAN,
    ) -> FeatureFlagEntity:
        async with self.uow:
            # 1. Check uniqueness
            existing_flag = await self.uow.feature_flags.get_by_key_and_project(key, project_id)
            if existing_flag:
                raise EntityAlreadyExistsException("Feature Flag with this key already exists in the project")

            # 2. Create the Flag
            flag = FeatureFlagEntity(
                name=name,
                key=key,
                project_id=project_id,
                description=description,
                type=flag_type,
                version=1,
            )
            await self.uow.feature_flags.add(flag)

            # 3. Create Default Variations if BOOLEAN
            false_var_id = None
            if flag_type == FlagType.BOOLEAN:
                true_var = FlagVariationEntity(feature_flag_id=flag.id, name="True", value=True)
                false_var = FlagVariationEntity(feature_flag_id=flag.id, name="False", value=False)
                await self.uow.flag_variations.add(true_var)
                await self.uow.flag_variations.add(false_var)
                false_var_id = false_var.id

            # 4. Create FeatureFlagEnvironment for all project environments
            environments = await self.uow.environments.list_for_project(project_id)
            for env in environments:
                state = FeatureFlagEnvironmentEntity(
                    feature_flag_id=flag.id,
                    environment_id=env.id,
                    is_enabled=False,
                    default_serve_variation_id=false_var_id,
                )
                await self.uow.feature_flag_environments.add(state)

            # 5. Audit Event
            audit = AuditEventEntity(
                organization_id=organization_id,
                user_id=user_id,
                entity_type=EntityType.FEATURE_FLAG,
                entity_id=flag.id,
                action=ActionType.CREATED,
                new_state={"name": name, "key": key, "type": flag_type.value},
            )
            await self.uow.audit_events.add(audit)

            # Single commit at the end ensures atomicity
            await self.uow.commit()
            return flag
