import uuid

from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagType,
    FlagVariationEntity,
    OutboxEventEntity,
    OutboxStatus,
)
from app.domain.events import FlagCreatedEvent
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
                    off_variation_id=false_var_id,
                )
                await self.uow.feature_flag_environments.add(state)

            # 5. Domain Event & Outbox
            event_dto = FlagCreatedEvent(
                aggregate_id=flag.id,
                flag_key=flag.key,
                version=flag.version,
                user_id=user_id,
                organization_id=organization_id,
                project_id=flag.project_id,
                name=flag.name,
                description=flag.description,
                flag_type=flag.type,
            )

            outbox_event = OutboxEventEntity(
                aggregate_type="feature_flag",
                aggregate_id=str(flag.id),
                event_type=event_dto.event_type,
                payload=event_dto.model_dump(mode="json"),
                status=OutboxStatus.PENDING,
            )
            await self.uow.outbox_events.add(outbox_event)

            # Single commit at the end ensures atomicity
            await self.uow.commit()
            return flag
