import uuid

from app.domain.entities import (
    ActionType,
    AuditEventEntity,
    EntityType,
    FeatureFlagEnvironmentEntity,
)
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

                # Audit Event
                action = ActionType.ENABLED if is_enabled else ActionType.DISABLED
                audit = AuditEventEntity(
                    organization_id=organization_id,
                    user_id=user_id,
                    entity_type=EntityType.FEATURE_FLAG_ENVIRONMENT,
                    entity_id=state.id,
                    action=action,
                    previous_state={"is_enabled": previous_enabled},
                    new_state={"is_enabled": is_enabled, "version": state.version},
                )
                await self.uow.audit_events.add(audit)

            await self.uow.commit()
            return state
