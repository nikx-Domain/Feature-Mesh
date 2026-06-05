from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import OutboxEventEntity, OutboxStatus
from app.domain.repositories.outbox_repository import OutboxEventRepository
from app.infrastructure.db.models import OutboxEvent


class SQLAlchemyOutboxEventRepository(OutboxEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: OutboxEventEntity) -> OutboxEventEntity:
        db_event = OutboxEvent(
            id=event.id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=event.payload,
            status=event.status,
            retry_count=event.retry_count,
            created_at=event.created_at,
            processed_at=event.processed_at,
        )
        self.session.add(db_event)
        return event

    async def get_pending_events(self, limit: int = 50) -> Sequence[OutboxEventEntity]:
        stmt = select(OutboxEvent).where(OutboxEvent.status == OutboxStatus.PENDING).limit(limit)
        result = await self.session.execute(stmt)
        return [
            OutboxEventEntity(
                id=db.id,
                aggregate_type=db.aggregate_type,
                aggregate_id=db.aggregate_id,
                event_type=db.event_type,
                payload=db.payload,
                status=db.status,
                retry_count=db.retry_count,
                created_at=db.created_at,
                processed_at=db.processed_at,
            )
            for db in result.scalars().all()
        ]

    async def update(self, event: OutboxEventEntity) -> OutboxEventEntity:
        stmt = select(OutboxEvent).where(OutboxEvent.id == event.id)
        result = await self.session.execute(stmt)
        db_event = result.scalars().first()
        if db_event:
            db_event.status = event.status
            db_event.retry_count = event.retry_count
            db_event.processed_at = event.processed_at
        return event
