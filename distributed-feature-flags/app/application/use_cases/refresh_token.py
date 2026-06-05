import uuid

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.domain.exceptions import AuthenticationException, PermissionDeniedException
from app.domain.unit_of_work import UnitOfWork


class RefreshTokenUseCase:
    """Use case to handle token refreshing within UOW boundaries."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, refresh_token: str) -> dict:
        # Decode and validate refresh token
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise AuthenticationException("Invalid token type: Refresh token required")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationException("Invalid token payload: Missing sub claim")

        async with self.uow:
            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                raise AuthenticationException("Invalid token payload: Invalid user ID format")

            user = await self.uow.users.get_by_id(user_id)
            if not user:
                raise AuthenticationException("User not found")

            if not user.is_active:
                raise PermissionDeniedException("User account is inactive")

            # Issue new token pair
            new_access_token = create_access_token(data={"sub": str(user.id)})
            new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
            }
