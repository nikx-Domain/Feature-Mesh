from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, create_refresh_token, verify_password
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Role, User


class LoginUseCase:
    """Use case to authenticate credentials and issue tokens within UOW boundaries."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, email: str, password: str) -> dict:
        async with self.uow:
            stmt = (
                select(User)
                .where(User.email == email)
                .options(selectinload(User.roles).selectinload(Role.permissions))
            )
            result = await self.uow.session.execute(stmt)
            user = result.scalars().first()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not verify_password(password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

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
