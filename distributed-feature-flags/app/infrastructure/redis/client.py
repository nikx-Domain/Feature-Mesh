import structlog
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Global Redis pool
_redis_pool: ConnectionPool | None = None


async def init_redis() -> None:
    """Initialize Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        logger.info("Initializing Redis connection pool")
        _redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            health_check_interval=30,
            max_connections=100,
        )


async def close_redis() -> None:
    """Close Redis connection pool gracefully."""
    global _redis_pool
    if _redis_pool is not None:
        logger.info("Closing Redis connection pool")
        await _redis_pool.disconnect()
        _redis_pool = None


def get_redis_client() -> Redis:
    """Get an async Redis client from the connection pool."""
    if _redis_pool is None:
        raise RuntimeError("Redis pool is not initialized. Call init_redis() first.")
    return Redis(connection_pool=_redis_pool)
