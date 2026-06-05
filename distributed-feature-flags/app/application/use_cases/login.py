from app.core.security import create_access_token, create_refresh_token, verify_password
from app.domain.exceptions import AuthenticationException, PermissionDeniedException
from app.domain.unit_of_work import UnitOfWork


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
                raise PermissionDeniedException("User account is inactive")

            user_id_str = str(user.id)
            access_token = create_access_token(data={"sub": user_id_str})
            refresh_token = create_refresh_token(data={"sub": user_id_str})

            # Returns tokens
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 1800,
            }
