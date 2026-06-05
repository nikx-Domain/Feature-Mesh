from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.domain.services.cache_service import CacheService
from app.infrastructure.cache.redis_cache_service import RedisCacheService
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator that injects a database session.
    Yields the session and ensures proper resource cleanup on exit.
    """
    async with SessionLocal() as session:
        yield session


async def get_uow(db: AsyncSession = Depends(get_db)) -> SQLAlchemyUnitOfWork:
    """Dependency injection provider for SQLAlchemyUnitOfWork."""
    return SQLAlchemyUnitOfWork(db)


async def get_cache_service() -> CacheService:
    """Dependency injection provider for CacheService."""
    return RedisCacheService()
