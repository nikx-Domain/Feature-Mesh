from app.core.security import create_access_token, create_refresh_token, verify_password, decode_token
from app.domain.exceptions import AuthenticationException, PermissionDeniedException
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import RefreshToken
import datetime
import structlog

logger = structlog.get_logger(__name__)


class LoginUseCase:
    """Use case to authenticate credentials and issue tokens within UOW boundaries."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, email: str, password: str) -> dict:
        async with self.uow:
            user = await self.uow.users.get_by_email(email)

            if not user:
                raise AuthenticationException("Invalid credentials")

            if not verify_password(password, user.password_hash):
                raise AuthenticationException("Invalid credentials")

            if not user.is_active:
                logger.warning("login_failure", email=email, reason="inactive_account")
                raise PermissionDeniedException("User account is inactive")

            user_id_str = str(user.id)
            access_token = create_access_token(data={"sub": user_id_str})
            refresh_token = create_refresh_token(data={"sub": user_id_str})

            # Decode to get jti and exp
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            exp_timestamp = payload.get("exp")
            expires_at = datetime.datetime.fromtimestamp(exp_timestamp, datetime.UTC)

            rt_model = RefreshToken(
                jti=jti,
                user_id=user.id,
                expires_at=expires_at,
                is_revoked=False
            )
            await self.uow.refresh_tokens.create(rt_model)

            logger.info("login_success", user_id=user_id_str, email=email)

            # Returns tokens
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
            }
