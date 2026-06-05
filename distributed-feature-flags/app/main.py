from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.logging import setup_logging
from app.core.database import SessionLocal
from app.infrastructure.kafka.client import close_kafka_producer, init_kafka_producer
from app.infrastructure.background.outbox_publisher import outbox_publisher
from app.infrastructure.kafka.consumers.cache_consumer import CacheInvalidationConsumer
from app.infrastructure.kafka.consumers.audit_consumer import AuditConsumer
from app.domain.services.cache_service import CacheService
from app.infrastructure.redis.client import close_redis, get_redis_client, init_redis
from app.presentation.api.auth import router as auth_router
from app.presentation.api.cache import router as cache_router
from app.presentation.api.evaluation import router as evaluation_router
from app.presentation.api.feature_flags import router as feature_flags_router
from app.presentation.api.handlers import register_exception_handlers
from app.presentation.api.tenancy import router as tenancy_router
from app.presentation.middleware.authorization import JWTAuthorizationMiddleware

# Initialize structured logging configurations
setup_logging()
logger = structlog.get_logger(__name__)

cache_consumer: CacheInvalidationConsumer | None = None
audit_consumer: AuditConsumer | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache_consumer, audit_consumer
    await init_redis()
    await init_kafka_producer()
    await outbox_publisher.start()

    redis_client = get_redis_client()
    cache_service = CacheService(redis_client)
    cache_consumer = CacheInvalidationConsumer(cache_service)
    audit_consumer = AuditConsumer(SessionLocal)

    await cache_consumer.start()
    await audit_consumer.start()

    yield

    if cache_consumer:
        await cache_consumer.stop()
    if audit_consumer:
        await audit_consumer.stop()
    
    await outbox_publisher.stop()
    await close_kafka_producer()
    await close_redis()

app = FastAPI(
    title="Distributed Feature Flag Platform",
    description="Production-grade distributed feature flags control plane backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware for cross-origin access configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(JWTAuthorizationMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(tenancy_router, prefix="/api/v1")
app.include_router(feature_flags_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")

register_exception_handlers(app)


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check route validating core API runtime state and PostgreSQL connectivity.
    """
    try:
        # Query database to confirm healthy connection pool
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error("Database connectivity check failed", error=str(e))
        db_status = "unhealthy"

    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error("Redis connectivity check failed", error=str(e))
        redis_status = "unhealthy"

    status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "unhealthy"
    return {
        "status": status,
        "environment": settings.APP_ENV,
        "services": {
            "database": db_status,
            "redis": redis_status,
        },
    }
