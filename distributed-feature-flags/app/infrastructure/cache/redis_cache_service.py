import structlog
from redis.exceptions import RedisError

from app.domain.services.cache_service import CacheService
from app.infrastructure.redis.client import get_redis_client
from app.core.metrics import (
    REDIS_CACHE_HITS_TOTAL,
    REDIS_CACHE_MISSES_TOTAL,
    REDIS_CACHE_REBUILDS_TOTAL,
    REDIS_CACHE_ERRORS_TOTAL
)

logger = structlog.get_logger(__name__)


class RedisCacheService(CacheService):
    """Redis implementation of the CacheService interface."""

    async def get(self, key: str) -> str | None:
        try:
            client = get_redis_client()
            value = await client.get(key)
            if isinstance(value, bytes):
                REDIS_CACHE_HITS_TOTAL.inc()
                return value.decode("utf-8")
            if isinstance(value, str):
                REDIS_CACHE_HITS_TOTAL.inc()
                return value
            
            REDIS_CACHE_MISSES_TOTAL.inc()
            return None
        except RedisError as e:
            REDIS_CACHE_ERRORS_TOTAL.labels(action="get").inc()
            logger.error("Redis GET failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> None:
        try:
            client = get_redis_client()
            await client.set(key, value, ex=expire_seconds)
            REDIS_CACHE_REBUILDS_TOTAL.inc()
        except RedisError as e:
            REDIS_CACHE_ERRORS_TOTAL.labels(action="set").inc()
            logger.error("Redis SET failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            client = get_redis_client()
            await client.delete(key)
        except RedisError as e:
            REDIS_CACHE_ERRORS_TOTAL.labels(action="delete").inc()
            logger.error("Redis DELETE failed", key=key, error=str(e))

    async def exists(self, key: str) -> bool:
        try:
            client = get_redis_client()
            result = await client.exists(key)
            if result:
                REDIS_CACHE_HITS_TOTAL.inc()
            else:
                REDIS_CACHE_MISSES_TOTAL.inc()
            return bool(result)
        except RedisError as e:
            REDIS_CACHE_ERRORS_TOTAL.labels(action="exists").inc()
            logger.error("Redis EXISTS failed", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> None:
        try:
            client = get_redis_client()
            # scan_iter automatically handles cursor traversal
            async for key in client.scan_iter(match=pattern, count=100):
                await client.delete(key)
        except RedisError as e:
            REDIS_CACHE_ERRORS_TOTAL.labels(action="delete_pattern").inc()
            logger.error("Redis DELETE PATTERN failed", pattern=pattern, error=str(e))
