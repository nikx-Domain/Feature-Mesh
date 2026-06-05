import uuid

from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.evaluation.models import EvaluationContext, EvaluationDecision
from app.domain.exceptions import EntityNotFoundException
from app.domain.unit_of_work import UnitOfWork


class EvaluateFeatureFlagUseCase:
    """Use case to evaluate a feature flag for a given context in a specific environment."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        environment_id: uuid.UUID,
        flag_key: str,
        context: EvaluationContext,
    ) -> EvaluationDecision:
        async with self.uow:
            # 1. Fetch the environment to get its project ID
            env = await self.uow.environments.get_by_id(environment_id)
            if not env or env.deleted_at:
                raise EntityNotFoundException("Environment not found")

            # 2. Fetch the feature flag by key within the project
            flag = await self.uow.feature_flags.get_by_key_and_project(flag_key, env.project_id)
            if not flag or flag.is_archived or flag.deleted_at:
                raise EntityNotFoundException("Feature flag not found or is archived")

            # 3. Fetch the environment-specific state of the flag (includes rules)
            state = await self.uow.feature_flag_environments.get_by_flag_and_environment(
                flag.id, environment_id
            )
            if not state:
                raise EntityNotFoundException("Feature flag environment state not found")

            # 4. Fetch the available variations
            variations = list(await self.uow.flag_variations.list_for_flag(flag.id))

            # 5. Evaluate the flag
            decision = evaluate_feature_flag(
                flag=flag,
                environment=state,
                variations=variations,
                context=context,
            )

            return decision
