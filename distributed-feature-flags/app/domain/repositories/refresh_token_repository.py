import uuid
from abc import ABC, abstractmethod

from app.infrastructure.db.models import RefreshToken

class RefreshTokenRepository(ABC):
    @abstractmethod
    async def create(self, refresh_token: RefreshToken) -> RefreshToken:
        pass

    @abstractmethod
    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        pass

    @abstractmethod
    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        pass
