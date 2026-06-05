import uuid

import structlog

from app.domain.cache.models import EvaluationDataCacheDTO
from app.domain.services.cache_service import CacheService
from app.domain.unit_of_work import UnitOfWork

logger = structlog.get_logger(__name__)


class CacheWarmupService:
    def __init__(self, uow: UnitOfWork, cache_service: CacheService):
        self.uow = uow
        self.cache_service = cache_service

    async def warmup_environment(self, environment_id: uuid.UUID) -> int:
        """Warms up the cache for all active flags in a given environment. Returns count of flags cached."""
        count = 0
        async with self.uow:
            env = await self.uow.environments.get_by_id(environment_id)
            if not env or env.deleted_at:
                return 0

            flags = await self.uow.feature_flags.list_for_project(env.project_id)
            for flag in flags:
                if flag.is_archived or flag.deleted_at:
                    continue

                state = await self.uow.feature_flag_environments.get_by_flag_and_environment(
                    flag.id, environment_id
                )
                if not state:
                    continue

                variations = list(await self.uow.flag_variations.list_for_flag(flag.id))

                dto = EvaluationDataCacheDTO(
                    flag=flag,
                    environment=state,
                    variations=variations,
                )

                version = state.version
                data_key = f"eval_data:{environment_id}:{flag.key}:v{version}"
                pointer_key = f"eval_ptr:{environment_id}:{flag.key}"

                await self.cache_service.set(data_key, dto.model_dump_json(), expire_seconds=3600)
                await self.cache_service.set(pointer_key, str(version), expire_seconds=3600)
                count += 1

        logger.info("Environment cache warm-up complete", environment_id=str(environment_id), count=count)
        return count
