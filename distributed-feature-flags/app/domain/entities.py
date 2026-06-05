import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlagType(str, Enum):
    BOOLEAN = "boolean"
    MULTIVARIATE = "multivariate"


class ActionType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class EntityType(str, Enum):
    FEATURE_FLAG = "feature_flag"
    FEATURE_FLAG_ENVIRONMENT = "feature_flag_environment"


class TargetingOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES_REGEX = "matches_regex"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


class DomainEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FlagVariationEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    feature_flag_id: uuid.UUID
    name: str
    value: dict[str, Any] | str | bool | None = None


class TargetingRuleEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    feature_flag_environment_id: uuid.UUID
    attribute: str
    operator: TargetingOperator
    value: dict[str, Any] | str | list[Any] | None = None
    serve_variation_id: uuid.UUID
    priority: int = 0

    @model_validator(mode="after")
    def validate_regex_pattern(self) -> "TargetingRuleEntity":
        if self.operator == TargetingOperator.MATCHES_REGEX and isinstance(self.value, str):
            try:
                re.compile(self.value)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {self.value}") from e
        return self


class RolloutRuleEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    feature_flag_environment_id: uuid.UUID
    serve_variation_id: uuid.UUID
    percentage: int = Field(ge=0, le=100)


class FeatureFlagEnvironmentEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    feature_flag_id: uuid.UUID
    environment_id: uuid.UUID
    is_enabled: bool = False
    default_serve_variation_id: uuid.UUID | None = None
    off_variation_id: uuid.UUID | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    targeting_rules: list[TargetingRuleEntity] = Field(default_factory=list)
    rollout_rules: list[RolloutRuleEntity] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rollout_rules_percentage(self) -> "FeatureFlagEnvironmentEntity":
        total_percentage = sum(rule.percentage for rule in self.rollout_rules)
        if total_percentage > 100:
            raise ValueError(f"Total percentage of rollout rules cannot exceed 100, got {total_percentage}")
        return self


class FeatureFlagEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    name: str
    key: str
    description: str | None = None
    type: FlagType = FlagType.BOOLEAN
    version: int = 1
    is_archived: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = None


class AuditEventEntity(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    organization_id: uuid.UUID
    user_id: uuid.UUID | None = None
    entity_type: EntityType
    entity_id: uuid.UUID
    action: ActionType
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
