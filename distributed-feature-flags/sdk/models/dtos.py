from typing import Any
from pydantic import BaseModel, Field

class SDKTargetingRuleDTO(BaseModel):
    id: str
    attribute: str
    operator: str
    value: Any
    serve_variation_id: str
    priority: int

class SDKRolloutRuleDTO(BaseModel):
    id: str
    percentage: int
    serve_variation_id: str

class SDKFeatureFlagEnvironmentDTO(BaseModel):
    is_enabled: bool
    default_serve_variation_id: str | None = None
    off_variation_id: str | None = None
    targeting_rules: list[SDKTargetingRuleDTO] = Field(default_factory=list)
    rollout_rules: list[SDKRolloutRuleDTO] = Field(default_factory=list)

class SDKFlagVariationDTO(BaseModel):
    id: str
    name: str
    value: Any

class SDKFeatureFlagDTO(BaseModel):
    id: str
    key: str
    type: str
    version: int
    environment: SDKFeatureFlagEnvironmentDTO
    variations: list[SDKFlagVariationDTO]

class SDKSnapshotDTO(BaseModel):
    environment_id: str
    flags: dict[str, SDKFeatureFlagDTO]
