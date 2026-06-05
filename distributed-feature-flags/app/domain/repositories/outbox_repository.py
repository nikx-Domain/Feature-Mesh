from abc import ABC, abstractmethod
from typing import Sequence

from app.domain.entities import OutboxEventEntity


class OutboxEventRepository(ABC):
    @abstractmethod
    async def add(self, event: OutboxEventEntity) -> OutboxEventEntity:
        pass

    @abstractmethod
    async def get_pending_events(self, limit: int = 50) -> Sequence[OutboxEventEntity]:
        pass

    @abstractmethod
    async def update(self, event: OutboxEventEntity) -> OutboxEventEntity:
        pass
