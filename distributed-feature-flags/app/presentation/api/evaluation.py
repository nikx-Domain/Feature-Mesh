import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.use_cases.evaluate_feature_flag import EvaluateFeatureFlagUseCase
from app.application.use_cases.get_environment_snapshot import GetEnvironmentSnapshotUseCase
from app.core.dependencies import get_cache_service, get_uow
from app.domain.evaluation.models import EvaluationContext, EvaluationDecision
from app.domain.services.cache_service import CacheService
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork

router = APIRouter(prefix="/environments", tags=["Evaluation"])


class EvaluateRequest(BaseModel):
    context: EvaluationContext


@router.post(
    "/{environment_id}/evaluate/{flag_key}",
    response_model=EvaluationDecision,
)
async def evaluate_flag(
    environment_id: uuid.UUID,
    flag_key: str,
    body: EvaluateRequest,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
    cache_service: CacheService = Depends(get_cache_service),
):
    """
    Evaluates a specific feature flag for a given context in a specific environment.
    
    Note: Standard user authentication is intentionally omitted here to simulate 
    a server-side SDK endpoint. In a real system, this would be secured by an Environment SDK Key.
    """
    use_case = EvaluateFeatureFlagUseCase(uow, cache_service)
    decision = await use_case.execute(
        environment_id=environment_id,
        flag_key=flag_key,
        context=body.context,
    )
    return decision


@router.get(
    "/{environment_id}/snapshot",
)
async def get_environment_snapshot(
    environment_id: uuid.UUID,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """
    Returns a complete snapshot of all feature flags and their rules for an environment.
    This is intended to be used by Server-Side SDKs to build a local cache for offline evaluation.
    
    Note: Authentication is omitted to simulate a server-side SDK endpoint.
    """
    use_case = GetEnvironmentSnapshotUseCase(uow)
    snapshot = await use_case.execute(environment_id=environment_id)
    return snapshot
