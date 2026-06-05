import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Base class for all domain events."""
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: uuid.UUID
    flag_key: str
    version: int
    user_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None


class FlagCreatedEvent(DomainEvent):
    event_type: str = "flag.created"
    project_id: uuid.UUID
    name: str
    description: str | None
    flag_type: str


class FlagUpdatedEvent(DomainEvent):
    event_type: str = "flag.updated"
    previous_state: dict[str, Any]
    new_state: dict[str, Any]


class FlagArchivedEvent(DomainEvent):
    event_type: str = "flag.archived"


class FlagToggledEvent(DomainEvent):
    event_type: str = "flag.toggled"
    environment_id: uuid.UUID
    is_enabled: bool
