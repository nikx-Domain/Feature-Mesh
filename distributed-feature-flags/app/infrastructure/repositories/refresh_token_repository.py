import uuid
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.db.models import RefreshToken

class SQLAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, refresh_token: RefreshToken) -> RefreshToken:
        self.session.add(refresh_token)
        return refresh_token

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = update(RefreshToken).where(RefreshToken.user_id == user_id).values(is_revoked=True)
        await self.session.execute(stmt)
