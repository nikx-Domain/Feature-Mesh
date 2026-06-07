import asyncio
import structlog
from aiokafka import AIOKafkaConsumer
from app.core.config import settings
from app.observability.kafka_metrics import (
    kafka_consumer_processed_total,
    kafka_consumer_failures_total,
)
from app.infrastructure.kafka.client import send_kafka_message

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
                
                max_retries = 3
                success = False
                for attempt in range(max_retries):
                    try:
                        await self.process_message(msg)
                        success = True
                        break
                    except Exception as e:
                        logger.warning("Message processing failed, retrying", attempt=attempt, error=str(e))
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                
                if not success:
                    logger.error("Message failed after max retries, sending to DLQ", topic=msg.topic)
                    # Send to DLQ
                    await send_kafka_message(
                        topic="dead_letter_events",
                        value=msg.value,
                        key=msg.key,
                        headers=[
                            ("original_topic", msg.topic.encode("utf-8")),
                            ("group_id", self.group_id.encode("utf-8")),
                        ]
                    )
                    kafka_consumer_failures_total.labels(topic=msg.topic).inc()
                else:
                    kafka_consumer_processed_total.labels(topic=msg.topic).inc()

                await self._consumer.commit()
            except Exception as e:
                if not self._running:
                    break
                logger.error("Consumer loop error", group_id=self.group_id, error=str(e))
                await asyncio.sleep(1)

    async def process_message(self, msg) -> None:
        raise NotImplementedError
