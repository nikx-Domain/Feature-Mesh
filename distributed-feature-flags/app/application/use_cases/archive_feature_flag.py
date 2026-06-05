import uuid

from app.domain.entities import (
    FeatureFlagEntity,
    OutboxEventEntity,
    OutboxStatus,
)
from app.domain.events import FlagArchivedEvent
from app.domain.exceptions import EntityNotFoundException
from app.domain.unit_of_work import UnitOfWork


class ArchiveFeatureFlagUseCase:
    """Use case to handle soft-deleting (archiving) a feature flag."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        flag_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> FeatureFlagEntity:
        async with self.uow:
            flag = await self.uow.feature_flags.get_by_id(flag_id)
            if not flag or flag.deleted_at:
                raise EntityNotFoundException("Feature Flag not found")

            if not flag.is_archived:
                flag.is_archived = True
                flag.version += 1
                await self.uow.feature_flags.update(flag)

                # Domain Event
                event_dto = FlagArchivedEvent(
                    aggregate_id=flag.id,
                    flag_key=flag.key,
                    version=flag.version,
                    user_id=user_id,
                    organization_id=organization_id,
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

            return flag
