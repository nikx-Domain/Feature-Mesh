import structlog
from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.infrastructure.resilience import kafka_circuit_breaker

logger = structlog.get_logger(__name__)

_producer: AIOKafkaProducer | None = None


async def init_kafka_producer() -> None:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id="feature-flags-api",
            acks="all",
            retry_backoff_ms=500,
            request_timeout_ms=10000,
        )
        try:
            await _producer.start()
            logger.info("Kafka producer initialized", bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.error("Failed to initialize Kafka producer", error=str(e))
            # Don't throw immediately on boot, we want graceful fallback
            _producer = None


async def close_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


def get_kafka_producer() -> AIOKafkaProducer | None:
    return _producer

@kafka_circuit_breaker
async def send_kafka_message(topic: str, value: bytes, key: bytes | None = None, headers: list[tuple[str, bytes]] | None = None) -> None:
    if _producer is None:
        raise RuntimeError("Kafka producer not initialized")
    await _producer.send_and_wait(topic, value=value, key=key, headers=headers)
