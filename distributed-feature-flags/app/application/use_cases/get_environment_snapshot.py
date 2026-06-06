import uuid
from typing import Any

from pydantic import BaseModel

from app.domain.exceptions import EntityNotFoundException
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork


class GetEnvironmentSnapshotUseCase:
    def __init__(self, uow: SQLAlchemyUnitOfWork):
        self.uow = uow

    async def execute(self, environment_id: uuid.UUID) -> dict[str, Any]:
        async with self.uow:
            env = await self.uow.environments.get_by_id(environment_id)
            if not env:
                raise EntityNotFoundException("Environment not found")

            # Fetch all flags for the environment's project
            flags = await self.uow.feature_flags.list_for_project(env.project_id)
            
            # Fetch all flag environments for this specific environment
            ff_envs = await self.uow.feature_flag_environments.list_for_environment(environment_id)
            ff_env_map = {ff_env.feature_flag_id: ff_env for ff_env in ff_envs}

            flags_data = {}
            for flag in flags:
                # Fetch variations
                variations = await self.uow.flag_variations.list_for_flag(flag.id)
                
                ff_env = ff_env_map.get(flag.id)
                if not ff_env:
                    continue
                    
                # We need targeting and rollout rules for this ff_env
                targeting_rules = await self.uow.targeting_rules.list_for_state(ff_env.id)
                rollout_rules = await self.uow.rollout_rules.list_for_state(ff_env.id)
                
                flags_data[flag.key] = {
                    "id": str(flag.id),
                    "key": flag.key,
                    "type": flag.type.value,
                    "version": flag.version,
                    "environment": {
                        "is_enabled": ff_env.is_enabled,
                        "default_serve_variation_id": str(ff_env.default_serve_variation_id) if ff_env.default_serve_variation_id else None,
                        "off_variation_id": str(ff_env.off_variation_id) if ff_env.off_variation_id else None,
                        "targeting_rules": [
                            {
                                "id": str(r.id),
                                "attribute": r.attribute,
                                "operator": r.operator.value,
                                "value": r.value,
                                "serve_variation_id": str(r.serve_variation_id),
                                "priority": r.priority
                            }
                            for r in targeting_rules
                        ],
                        "rollout_rules": [
                            {
                                "id": str(r.id),
                                "percentage": r.percentage,
                                "serve_variation_id": str(r.serve_variation_id)
                            }
                            for r in rollout_rules
                        ]
                    },
                    "variations": [
                        {
                            "id": str(v.id),
                            "name": v.name,
                            "value": v.value
                        }
                        for v in variations
                    ]
                }

            return {
                "environment_id": str(environment_id),
                "flags": flags_data
            }
