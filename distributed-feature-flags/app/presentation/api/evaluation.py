import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.use_cases.evaluate_feature_flag import EvaluateFeatureFlagUseCase
from app.core.dependencies import get_uow
from app.domain.evaluation.models import EvaluationContext, EvaluationDecision
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
):
    """
    Evaluates a specific feature flag for a given context in a specific environment.
    
    Note: Standard user authentication is intentionally omitted here to simulate 
    a server-side SDK endpoint. In a real system, this would be secured by an Environment SDK Key.
    """
    use_case = EvaluateFeatureFlagUseCase(uow)
    decision = await use_case.execute(
        environment_id=environment_id,
        flag_key=flag_key,
        context=body.context,
    )
    return decision
