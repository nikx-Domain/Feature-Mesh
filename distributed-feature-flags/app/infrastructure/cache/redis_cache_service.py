import structlog
from redis.exceptions import RedisError
import pybreaker

from app.domain.services.cache_service import CacheService
from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.resilience import redis_circuit_breaker
from app.observability.redis_metrics import (
    redis_cache_hits_total,
    redis_cache_misses_total,
    redis_cache_rebuilds_total,
    redis_cache_errors_total
)

logger = structlog.get_logger(__name__)


class RedisCacheService(CacheService):
    """Redis implementation of the CacheService interface."""

    @redis_circuit_breaker
    async def get(self, key: str) -> str | None:
        try:
            client = get_redis_client()
            value = await client.get(key)
            if isinstance(value, bytes):
                redis_cache_hits_total.inc()
                return value.decode("utf-8")
            if isinstance(value, str):
                redis_cache_hits_total.inc()
                return value
            
            redis_cache_misses_total.inc()
            return None
        except RedisError as e:
            redis_cache_errors_total.labels(action="get").inc()
            logger.error("Redis GET failed", key=key, error=str(e))
            return None
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Redis GET circuit breaker open", key=key)
            return None

    @redis_circuit_breaker
    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> None:
        try:
            client = get_redis_client()
            await client.set(key, value, ex=expire_seconds)
            redis_cache_rebuilds_total.inc()
        except RedisError as e:
            redis_cache_errors_total.labels(action="set").inc()
            logger.error("Redis SET failed", key=key, error=str(e))
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Redis SET circuit breaker open", key=key)

    @redis_circuit_breaker
    async def delete(self, key: str) -> None:
        try:
            client = get_redis_client()
            await client.delete(key)
        except RedisError as e:
            redis_cache_errors_total.labels(action="delete").inc()
            logger.error("Redis DELETE failed", key=key, error=str(e))
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Redis DELETE circuit breaker open", key=key)

    @redis_circuit_breaker
    async def exists(self, key: str) -> bool:
        try:
            client = get_redis_client()
            result = await client.exists(key)
            if result:
                redis_cache_hits_total.inc()
            else:
                redis_cache_misses_total.inc()
            return bool(result)
        except RedisError as e:
            redis_cache_errors_total.labels(action="exists").inc()
            logger.error("Redis EXISTS failed", key=key, error=str(e))
            return False
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Redis EXISTS circuit breaker open", key=key)
            return False

    @redis_circuit_breaker
    async def delete_pattern(self, pattern: str) -> None:
        try:
            client = get_redis_client()
            # scan_iter automatically handles cursor traversal
            async for key in client.scan_iter(match=pattern, count=100):
                await client.delete(key)
        except RedisError as e:
            redis_cache_errors_total.labels(action="delete_pattern").inc()
            logger.error("Redis DELETE PATTERN failed", pattern=pattern, error=str(e))
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Redis DELETE PATTERN circuit breaker open", pattern=pattern)
