import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr

from app.application.use_cases.login import LoginUseCase
from app.application.use_cases.refresh_token import RefreshTokenUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.core.dependencies import get_uow
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: RegisterRequest,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Register a new user account."""
    use_case = RegisterUserUseCase(uow)
    user = await use_case.execute(body.email, body.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Authenticate credentials and return access/refresh tokens."""
    use_case = LoginUseCase(uow)
    tokens = await use_case.execute(body.email, body.password)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Refresh access and refresh tokens using a valid refresh token."""
    use_case = RefreshTokenUseCase(uow)
    tokens = await use_case.execute(body.refresh_token)
    return tokens
