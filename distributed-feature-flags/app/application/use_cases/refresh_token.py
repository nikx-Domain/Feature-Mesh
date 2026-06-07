import uuid

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.domain.exceptions import AuthenticationException, PermissionDeniedException
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import RefreshToken
import datetime
import structlog

logger = structlog.get_logger(__name__)


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
                logger.warning("refresh_failure", user_id=user_id_str, reason="user_not_found")
                raise AuthenticationException("User not found")

            if not user.is_active:
                logger.warning("refresh_failure", user_id=user_id_str, reason="inactive_account")
                raise PermissionDeniedException("User account is inactive")

            jti = payload.get("jti")
            if not jti:
                logger.warning("refresh_failure", user_id=user_id_str, reason="missing_jti")
                raise AuthenticationException("Invalid token payload: Missing jti")

            existing_token = await self.uow.refresh_tokens.get_by_jti(jti)
            if not existing_token:
                logger.warning("refresh_failure", user_id=user_id_str, jti=jti, reason="token_not_found_in_db")
                raise AuthenticationException("Invalid token")

            if existing_token.is_revoked:
                # REPLAY ATTACK DETECTED
                logger.error("security_event", event_type="token_reuse", user_id=user_id_str, jti=jti)
                await self.uow.refresh_tokens.revoke_all_for_user(user.id)
                raise AuthenticationException("Token reuse detected, all sessions revoked")

            # Mark current token as revoked
            existing_token.is_revoked = True

            # Issue new token pair
            new_access_token = create_access_token(data={"sub": str(user.id)})
            new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

            # Save new refresh token
            new_payload = decode_token(new_refresh_token)
            new_jti = new_payload.get("jti")
            new_exp_timestamp = new_payload.get("exp")
            new_expires_at = datetime.datetime.fromtimestamp(new_exp_timestamp, datetime.UTC)

            rt_model = RefreshToken(
                jti=new_jti,
                user_id=user.id,
                expires_at=new_expires_at,
                is_revoked=False
            )
            await self.uow.refresh_tokens.create(rt_model)

            logger.info("refresh_success", user_id=user_id_str)

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
            }
