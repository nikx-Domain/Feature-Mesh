import uuid

from app.domain.entities import (
    ActionType,
    AuditEventEntity,
    EntityType,
    FeatureFlagEntity,
)
from app.domain.exceptions import EntityNotFoundException
from app.domain.services.cache_service import CacheService
from app.domain.unit_of_work import UnitOfWork


class ArchiveFeatureFlagUseCase:
    """Use case to handle soft-deleting (archiving) a feature flag."""

    def __init__(self, uow: UnitOfWork, cache_service: CacheService) -> None:
        self.uow = uow
        self.cache_service = cache_service

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

                # Audit Event
                audit = AuditEventEntity(
                    organization_id=organization_id,
                    user_id=user_id,
                    entity_type=EntityType.FEATURE_FLAG,
                    entity_id=flag.id,
                    action=ActionType.ARCHIVED,
                    previous_state={"is_archived": False},
                    new_state={"is_archived": True, "version": flag.version},
                )
                await self.uow.audit_events.add(audit)

            await self.uow.commit()

            if not flag.is_archived: # Wait, we just set it to True! We should check if we DID archive it.
                pass

            # Since we just archived it, let's unconditionally invalidate.
            try:
                await self.cache_service.delete_pattern(f"eval_ptr:*:{flag.key}")
                await self.cache_service.delete_pattern(f"eval_data:*:{flag.key}:*")
            except Exception:
                pass

            return flag
