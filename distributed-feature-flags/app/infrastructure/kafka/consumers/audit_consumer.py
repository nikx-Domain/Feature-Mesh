import json
import uuid
import structlog
from typing import Callable
from aiokafka.structs import ConsumerRecord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.kafka.consumers.base import BaseConsumer
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.domain.entities import AuditEventEntity, ActionType, EntityType
from app.infrastructure.db.models import ProcessedKafkaEvent

logger = structlog.get_logger(__name__)

class AuditConsumer(BaseConsumer):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        super().__init__(group_id="audit-consumer-group", topics=["flag-events"])
        self.session_factory = session_factory

    async def process_message(self, msg: ConsumerRecord) -> None:
        headers = {k: v.decode("utf-8") if v else "" for k, v in (msg.headers or [])}
        event_type = headers.get("event_type")
        event_id = headers.get("event_id")

        if not event_type or not event_id:
            return
            
        async with self.session_factory() as session:
            # 1. Idempotency Check
            result = await session.execute(select(ProcessedKafkaEvent).where(ProcessedKafkaEvent.event_id == event_id))
            if result.scalars().first():
                logger.debug("Event already processed", event_id=event_id)
                return
                
            session.add(ProcessedKafkaEvent(event_id=event_id))
            
            uow = SQLAlchemyUnitOfWork(session)
            payload = json.loads(msg.value.decode("utf-8"))
            
            action_map = {
                "flag.created": ActionType.CREATED,
                "flag.updated": ActionType.UPDATED,
                "flag.archived": ActionType.ARCHIVED,
            }
            
            action = action_map.get(event_type)
            if event_type == "flag.toggled":
                action = ActionType.ENABLED if payload.get("is_enabled") else ActionType.DISABLED
                
            if action:
                user_id_str = payload.get("user_id")
                org_id_str = payload.get("organization_id")
                
                user_id = uuid.UUID(user_id_str) if user_id_str else None
                org_id = uuid.UUID(org_id_str) if org_id_str else uuid.uuid4() # Fallback for org_id if not present
                
                entity_type = EntityType.FEATURE_FLAG
                if event_type == "flag.toggled":
                    entity_type = EntityType.FEATURE_FLAG_ENVIRONMENT
                    
                audit = AuditEventEntity(
                    organization_id=org_id,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=uuid.UUID(payload.get("aggregate_id")),
                    action=action,
                    previous_state=payload.get("previous_state"),
                    new_state=payload.get("new_state", payload), # Fallback: use payload as new_state if not explicitly provided
                )
                
                await uow.audit_events.add(audit)
                
            await session.commit()
            logger.info("Processed audit event", event_id=event_id, event_type=event_type)
