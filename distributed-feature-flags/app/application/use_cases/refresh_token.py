import uuid

from fastapi import HTTPException, status

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import User


class RefreshTokenUseCase:
    """Use case to handle token refreshing within UOW boundaries."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, refresh_token: str) -> dict:
        # Decode and validate refresh token
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: Refresh token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: Missing sub claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        async with self.uow:
            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload: Invalid user ID format",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user = await self.uow.session.get(User, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Issue new token pair
            new_access_token = create_access_token(data={"sub": str(user.id)})
            new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
            }
