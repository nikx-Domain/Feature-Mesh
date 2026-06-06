import asyncio
import json
from datetime import UTC, datetime
from typing import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import OutboxStatus
from app.infrastructure.kafka.client import get_kafka_producer
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.core.database import SessionLocal
from app.core.metrics import (
    KAFKA_EVENTS_PUBLISHED_TOTAL,
    KAFKA_EVENTS_FAILED_TOTAL,
    OUTBOX_EVENTS_PENDING,
    OUTBOX_EVENTS_PROCESSED_TOTAL
)

logger = structlog.get_logger(__name__)


class OutboxPublisher:
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Outbox publisher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Outbox publisher stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.publish_pending_events()
            except Exception as e:
                logger.error("Outbox publisher encountered error", error=str(e))

            await asyncio.sleep(2.0)  # Polling interval

    async def publish_pending_events(self) -> None:
        producer = get_kafka_producer()
        if not producer:
            logger.warning("Kafka producer not available, skipping outbox publish")
            return

        async with self.session_factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            async with uow:
                events = await uow.outbox_events.get_pending_events(limit=100)
                
                # Update pending gauge (approximate via the count of pending fetched + assumes more exist, or we can just count).
                # To be precise we could count the pending rows, but for performance, we update gauge based on what's fetched.
                # Actually, gauge is best updated from a real COUNT query if possible, but let's just set it to len(events) for now.
                OUTBOX_EVENTS_PENDING.set(len(events))

                if not events:
                    return

                for event in events:
                    try:
                        payload_str = event.payload if isinstance(event.payload, str) else json.dumps(event.payload)
                        payload_bytes = payload_str.encode("utf-8")
                        key_bytes = event.aggregate_id.encode("utf-8")

                        await producer.send_and_wait(
                            topic="flag-events",
                            value=payload_bytes,
                            key=key_bytes,
                            headers=[
                                ("event_type", event.event_type.encode("utf-8")),
                                ("event_id", str(event.id).encode("utf-8")),
                            ],
                        )

                        event.status = OutboxStatus.PROCESSED
                        event.processed_at = datetime.now(UTC)
                        await uow.outbox_events.update(event)
                        
                        KAFKA_EVENTS_PUBLISHED_TOTAL.labels(topic="flag-events").inc()
                        OUTBOX_EVENTS_PROCESSED_TOTAL.inc()
                        logger.info("Published outbox event to Kafka", event_id=str(event.id))

                    except Exception as e:
                        KAFKA_EVENTS_FAILED_TOTAL.labels(topic="flag-events").inc()
                        logger.error("Failed to publish outbox event", event_id=str(event.id), error=str(e))
                        event.retry_count += 1
                        if event.retry_count > 5:
                            event.status = OutboxStatus.FAILED
                        await uow.outbox_events.update(event)

                await uow.commit()

outbox_publisher = OutboxPublisher(SessionLocal)
