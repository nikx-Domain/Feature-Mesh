from pydantic import BaseModel, ConfigDict

from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
    FlagVariationEntity,
)


class EvaluationDataCacheDTO(BaseModel):
    """Aggregated cache model for evaluating a feature flag.
    Uses pure Pydantic domain entities avoiding ORM serialization logic.
    """
    model_config = ConfigDict(from_attributes=True)

    flag: FeatureFlagEntity
    environment: FeatureFlagEnvironmentEntity
    variations: list[FlagVariationEntity]
