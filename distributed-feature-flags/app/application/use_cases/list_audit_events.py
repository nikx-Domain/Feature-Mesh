import uuid
from collections.abc import Sequence

from app.domain.entities import AuditEventEntity
from app.domain.unit_of_work import UnitOfWork


class ListAuditEventsUseCase:
    """Use case to handle listing audit events for an organization or specific entity."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        organization_id: uuid.UUID,
        entity_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[AuditEventEntity]:
        async with self.uow:
            if entity_id and entity_type:
                # Assuming entity access is already validated at the controller level
                # This could be used for getting the version history of a specific feature flag
                return await self.uow.audit_events.list_for_entity(entity_id, entity_type)
            else:
                return await self.uow.audit_events.list_for_organization(organization_id, limit, offset)
