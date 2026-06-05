import uuid

from app.domain.entities import (
    ActionType,
    AuditEventEntity,
    EntityType,
    FeatureFlagEntity,
)
from app.domain.exceptions import EntityNotFoundException
from app.domain.unit_of_work import UnitOfWork


class UpdateFeatureFlagUseCase:
    """Use case to handle updating a feature flag's basic properties."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        flag_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> FeatureFlagEntity:
        async with self.uow:
            flag = await self.uow.feature_flags.get_by_id(flag_id)
            if not flag or flag.is_archived or flag.deleted_at:
                raise EntityNotFoundException("Feature Flag not found or is archived")

            previous_state = {"name": flag.name, "description": flag.description}
            new_state = {}

            if name is not None and name != flag.name:
                flag.name = name
                new_state["name"] = name

            if description is not None and description != flag.description:
                flag.description = description
                new_state["description"] = description

            if new_state:
                flag.version += 1
                await self.uow.feature_flags.update(flag)

                # Audit Event
                audit = AuditEventEntity(
                    organization_id=organization_id,
                    user_id=user_id,
                    entity_type=EntityType.FEATURE_FLAG,
                    entity_id=flag.id,
                    action=ActionType.UPDATED,
                    previous_state=previous_state,
                    new_state={"name": flag.name, "description": flag.description, "version": flag.version},
                )
                await self.uow.audit_events.add(audit)

            await self.uow.commit()
            return flag
