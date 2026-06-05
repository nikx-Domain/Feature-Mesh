import uuid

from fastapi import APIRouter, Depends, status

from app.application.services.cache_warmup_service import CacheWarmupService
from app.core.dependencies import get_cache_service, get_uow
from app.domain.services.cache_service import CacheService
from app.infrastructure.db.models import OrgRole
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.presentation.api.dependencies import require_org_roles

router = APIRouter(prefix="/admin/cache", tags=["Cache Management"])

@router.post(
    "/warmup/environments/{environment_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def warmup_environment_cache(
    environment_id: uuid.UUID,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
    cache_service: CacheService = Depends(get_cache_service),
):
    """Pre-warm evaluation cache for a specific environment."""
    service = CacheWarmupService(uow, cache_service)
    count = await service.warmup_environment(environment_id)
    return {"message": "Cache warmup successful", "cached_flags_count": count}
