import json
import structlog
from aiokafka.structs import ConsumerRecord

from app.infrastructure.kafka.consumers.base import BaseConsumer
from app.domain.services.cache_service import CacheService

logger = structlog.get_logger(__name__)

class CacheInvalidationConsumer(BaseConsumer):
    def __init__(self, cache_service: CacheService):
        super().__init__(group_id="cache-invalidator-group", topics=["flag-events"])
        self.cache_service = cache_service

    async def process_message(self, msg: ConsumerRecord) -> None:
        headers = {k: v.decode("utf-8") if v else "" for k, v in (msg.headers or [])}
        event_type = headers.get("event_type")
        event_id = headers.get("event_id")

        if not event_type or not event_id:
            logger.warning("Message missing headers", offset=msg.offset)
            return
            
        try:
            payload = json.loads(msg.value.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to decode message", offset=msg.offset, error=str(e))
            return
            
        flag_key = payload.get("flag_key")
        if not flag_key:
            logger.warning("Event missing flag_key, skipping cache invalidation", event_id=event_id)
            return

        try:
            if event_type == "flag.created":
                pass
            elif event_type in ("flag.updated", "flag.archived"):
                await self.cache_service.delete_pattern(f"eval_ptr:*:{flag_key}")
                await self.cache_service.delete_pattern(f"eval_data:*:{flag_key}:*")
            elif event_type == "flag.toggled":
                env_id = payload.get("environment_id")
                if env_id:
                    await self.cache_service.delete(f"eval_ptr:{env_id}:{flag_key}")
                    await self.cache_service.delete_pattern(f"eval_data:{env_id}:{flag_key}:*")
            
            logger.info("Processed cache invalidation", event_id=event_id, event_type=event_type)
        except Exception as e:
            logger.error("Failed to invalidate cache", event_id=event_id, error=str(e))
            raise e
