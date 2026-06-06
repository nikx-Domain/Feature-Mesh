import uuid

import structlog

from app.domain.cache.models import EvaluationDataCacheDTO
from app.domain.evaluation.evaluator import evaluate_feature_flag
from app.domain.evaluation.models import EvaluationContext, EvaluationDecision
from app.domain.exceptions import EntityNotFoundException
from app.domain.services.cache_service import CacheService
from app.domain.unit_of_work import UnitOfWork
from app.core.metrics import (
    FEATURE_FLAG_EVALUATIONS_TOTAL,
    FEATURE_FLAG_EVALUATION_FAILURES_TOTAL,
    FEATURE_FLAG_TARGETING_MATCHES_TOTAL,
    FEATURE_FLAG_ROLLOUT_MATCHES_TOTAL,
    FEATURE_FLAG_DISABLED_TOTAL,
    EVALUATION_DURATION_SECONDS
)
import time

logger = structlog.get_logger(__name__)


class EvaluateFeatureFlagUseCase:
    """Use case to evaluate a feature flag for a given context in a specific environment."""

    def __init__(self, uow: UnitOfWork, cache_service: CacheService) -> None:
        self.uow = uow
        self.cache_service = cache_service

    async def execute(
        self,
        environment_id: uuid.UUID,
        flag_key: str,
        context: EvaluationContext,
    ) -> EvaluationDecision:
        
        start_time = time.perf_counter()
        try:
            return await self._execute_internal(environment_id, flag_key, context, start_time)
        except Exception:
            FEATURE_FLAG_EVALUATION_FAILURES_TOTAL.labels(flag_key=flag_key).inc()
            raise

    async def _execute_internal(
        self,
        environment_id: uuid.UUID,
        flag_key: str,
        context: EvaluationContext,
        start_time: float,
    ) -> EvaluationDecision:

        # --- Redis Primary Read Path ---
        pointer_key = f"eval_ptr:{environment_id}:{flag_key}"
        version_str = await self.cache_service.get(pointer_key)

        if version_str:
            cache_key = f"eval_data:{environment_id}:{flag_key}:v{version_str}"
            cached_data_str = await self.cache_service.get(cache_key)

            if cached_data_str:
                try:
                    dto = EvaluationDataCacheDTO.model_validate_json(cached_data_str)
                    decision = evaluate_feature_flag(
                        flag=dto.flag,
                        environment=dto.environment,
                        variations=dto.variations,
                        context=context,
                    )
                    decision.metadata["cache_hit"] = True
                    decision.metadata["version"] = version_str
                    self._record_metrics(decision, time.perf_counter() - start_time)
                    return decision
                except Exception as e:
                    logger.error("Failed to parse cached evaluation data", error=str(e))
                    # Fallthrough to DB on corruption

        # --- Cache Miss -> Database Fallback ---
        async with self.uow:
            env = await self.uow.environments.get_by_id(environment_id)
            if not env or env.deleted_at:
                raise EntityNotFoundException("Environment not found")

            flag = await self.uow.feature_flags.get_by_key_and_project(flag_key, env.project_id)
            if not flag or flag.is_archived or flag.deleted_at:
                raise EntityNotFoundException("Feature flag not found or is archived")

            state = await self.uow.feature_flag_environments.get_by_flag_and_environment(
                flag.id, environment_id
            )
            if not state:
                raise EntityNotFoundException("Feature flag environment state not found")

            variations = list(await self.uow.flag_variations.list_for_flag(flag.id))

            decision = evaluate_feature_flag(
                flag=flag,
                environment=state,
                variations=variations,
                context=context,
            )
            decision.metadata["cache_hit"] = False
            decision.metadata["version"] = str(state.version)

            # --- Cache Rebuild ---
            try:
                dto = EvaluationDataCacheDTO(
                    flag=flag,
                    environment=state,
                    variations=variations,
                )
                version = state.version

                # Write versioned data first (expire in 1 hour)
                data_key = f"eval_data:{environment_id}:{flag_key}:v{version}"
                await self.cache_service.set(data_key, dto.model_dump_json(), expire_seconds=3600)

                # Then update pointer (expire in 1 hour)
                await self.cache_service.set(pointer_key, str(version), expire_seconds=3600)
            except Exception as e:
                logger.error("Failed to write to cache during rebuild", error=str(e))

            self._record_metrics(decision, time.perf_counter() - start_time)
            return decision

    def _record_metrics(self, decision: EvaluationDecision, duration: float):
        EVALUATION_DURATION_SECONDS.labels(flag_key=decision.feature_flag_key).observe(duration)
        
        FEATURE_FLAG_EVALUATIONS_TOTAL.labels(
            flag_key=decision.feature_flag_key, 
            reason=decision.reason
        ).inc()
        
        if decision.reason == "DISABLED":
            FEATURE_FLAG_DISABLED_TOTAL.labels(flag_key=decision.feature_flag_key).inc()
        elif decision.reason == "TARGETING_MATCH":
            FEATURE_FLAG_TARGETING_MATCHES_TOTAL.labels(flag_key=decision.feature_flag_key).inc()
        elif decision.reason == "ROLLOUT":
            FEATURE_FLAG_ROLLOUT_MATCHES_TOTAL.labels(flag_key=decision.feature_flag_key).inc()
