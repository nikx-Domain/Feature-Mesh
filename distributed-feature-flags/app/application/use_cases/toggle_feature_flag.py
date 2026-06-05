import uuid

from app.domain.entities import (
    FeatureFlagEnvironmentEntity,
    OutboxEventEntity,
    OutboxStatus,
)
from app.domain.events import FlagToggledEvent
from app.domain.exceptions import DomainException, EntityNotFoundException
from app.domain.unit_of_work import UnitOfWork


class ToggleFeatureFlagUseCase:
    """Use case to handle enabling or disabling a feature flag in a specific environment."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        feature_flag_id: uuid.UUID,
        environment_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        is_enabled: bool,
    ) -> FeatureFlagEnvironmentEntity:
        async with self.uow:
            state = await self.uow.feature_flag_environments.get_by_flag_and_environment(
                feature_flag_id, environment_id
            )

            if not state:
                raise EntityNotFoundException("Feature Flag Environment state not found")

            flag = await self.uow.feature_flags.get_by_id(feature_flag_id)
            if not flag or flag.is_archived or flag.deleted_at:
                raise DomainException("Cannot toggle an archived or deleted feature flag")

            if state.is_enabled != is_enabled:
                previous_enabled = state.is_enabled
                state.is_enabled = is_enabled
                state.version += 1
                await self.uow.feature_flag_environments.update(state)

                # Domain Event
                event_dto = FlagToggledEvent(
                    aggregate_id=flag.id,
                    flag_key=flag.key,
                    version=state.version,
                    user_id=user_id,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    is_enabled=is_enabled,
                )

                # Outbox Event
                outbox_event = OutboxEventEntity(
                    aggregate_type="feature_flag",
                    aggregate_id=str(flag.id),
                    event_type=event_dto.event_type,
                    payload=event_dto.model_dump(mode="json"),
                    status=OutboxStatus.PENDING,
                )
                await self.uow.outbox_events.add(outbox_event)

            await self.uow.commit()

            return state
