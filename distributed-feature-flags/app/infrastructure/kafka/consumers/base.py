import asyncio
import structlog
from aiokafka import AIOKafkaConsumer
from app.core.config import settings
from app.observability.kafka_metrics import (
    kafka_consumer_processed_total,
    kafka_consumer_failures_total,
)

logger = structlog.get_logger(__name__)

class BaseConsumer:
    def __init__(self, group_id: str, topics: list[str]):
        self.group_id = group_id
        self.topics = topics
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        try:
            await self._consumer.start()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Kafka consumer started", group_id=self.group_id, topics=self.topics)
        except Exception as e:
            logger.error("Failed to start Kafka consumer", group_id=self.group_id, error=str(e))
            self._running = False

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        logger.info("Kafka consumer stopped", group_id=self.group_id)

    async def _run_loop(self):
        if not self._consumer:
            return
        while self._running:
            try:
                msg = await self._consumer.getone()
                await self.process_message(msg)
                await self._consumer.commit()
                kafka_consumer_processed_total.labels(topic=msg.topic).inc()
            except Exception as e:
                if not self._running:
                    break
                logger.error("Error processing message", group_id=self.group_id, error=str(e))
                # We do not have msg.topic guaranteed if getone() fails, but if it failed in process_message we could.
                # Just use the first topic from self.topics as a fallback if msg is undefined
                topic = self.topics[0] if self.topics else "unknown"
                try:
                    if 'msg' in locals() and hasattr(msg, 'topic'):
                        topic = msg.topic
                except:
                    pass
                kafka_consumer_failures_total.labels(topic=topic).inc()
                await asyncio.sleep(1)

    async def process_message(self, msg) -> None:
        raise NotImplementedError
