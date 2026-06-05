import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationReason(str, Enum):
    TARGETING_MATCH = "TARGETING_MATCH"
    ROLLOUT = "ROLLOUT"
    DEFAULT = "DEFAULT"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class EvaluationContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class EvaluationDecision(BaseModel):
    feature_flag_key: str
    is_enabled: bool
    variation_id: uuid.UUID | None
    variation_value: Any
    reason: EvaluationReason
