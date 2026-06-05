import asyncio

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.application.decorators import require_permission
from app.application.use_cases.login import LoginUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.core.database import Base
from app.core.dependencies import get_db, get_uow
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.infrastructure.db.models import Permission, Role, User
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.main import app
from app.presentation.api.dependencies import require_permissions

# Setup in-memory SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=test_engine,
    class_=AsyncSession,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def override_get_uow(db: AsyncSession = Depends(override_get_db)):
    return SQLAlchemyUnitOfWork(db)


# FastAPI test client
client = TestClient(app)


# Test route to verify require_permissions dependency
@app.get("/test-protected-route", tags=["Test"])
async def protected_route(
    current_user: User = Depends(require_permissions("flag:create")),
):
    return {"message": "success", "email": current_user.email}


@pytest.fixture(autouse=True, scope="module")
def setup_test_database():
    # Initialize the database tables
    async def init():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init())

    # Apply FastAPI dependency overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_uow] = override_get_uow
    yield
    app.dependency_overrides.clear()

    # Drop database tables
    async def cleanup():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()

    asyncio.run(cleanup())


@pytest.fixture(autouse=True)
def clean_database_records():
    # Truncate tables before each test to guarantee test isolation
    async def clean():
        async with TestSessionLocal() as session:
            # For SQLite, we can just delete from tables
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
            await session.commit()

    asyncio.run(clean())


# ==========================================
# 1. SECURITY UTILITIES TESTS
# ==========================================


def test_password_hashing():
    password = "super_secure_password"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_operations():
    payload = {"sub": "test_user_id"}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    # Decode and verify
    decoded_access = decode_token(access_token)
    assert decoded_access["sub"] == "test_user_id"
    assert decoded_access["type"] == "access"

    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh["sub"] == "test_user_id"
    assert decoded_refresh["type"] == "refresh"


def test_jwt_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("invalid.token.value")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid token"


# ==========================================
# 2. APPLICATION USE CASE TESTS
# ==========================================


def test_user_registration_and_authentication():
    async def test():
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)

            # Register user
            reg_use_case = RegisterUserUseCase(uow)
            user = await reg_use_case.execute("user@test.com", "pass123")
            assert user.email == "user@test.com"
            assert user.is_active is True

            # Authenticate user successfully
            login_use_case = LoginUseCase(uow)
            tokens = await login_use_case.execute("user@test.com", "pass123")
            assert "access_token" in tokens
            assert "refresh_token" in tokens

            # Verify token sub payload matches user ID
            payload = decode_token(tokens["access_token"])
            assert payload["sub"] == str(user.id)

            # Authenticate with wrong password
            with pytest.raises(HTTPException) as exc_info:
                await login_use_case.execute("user@test.com", "wrong_pass")
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    asyncio.run(test())


def test_register_duplicate_email():
    async def test():
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)
            reg_use_case = RegisterUserUseCase(uow)
            await reg_use_case.execute("dup@test.com", "pass123")

            with pytest.raises(HTTPException) as exc_info:
                await reg_use_case.execute("dup@test.com", "pass456")
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    asyncio.run(test())


# ==========================================
# 3. ENDPOINT REGISTRATION, LOGIN & REFRESH TESTS
# ==========================================


def test_api_auth_flow_e2e():
    # 1. Register via endpoint
    reg_response = client.post(
        "/api/v1/auth/register",
        json={"email": "api_user@test.com", "password": "securepassword"},
    )
    assert reg_response.status_code == status.HTTP_201_CREATED
    assert reg_response.json()["email"] == "api_user@test.com"

    # 2. Login via endpoint
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "api_user@test.com", "password": "securepassword"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    data = login_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # 3. Refresh token via endpoint
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh_response.status_code == status.HTTP_200_OK
    ref_data = refresh_response.json()
    assert "access_token" in ref_data
    assert "refresh_token" in ref_data

    # 4. Refresh token with invalid format raises 401
    bad_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"},
    )
    assert bad_refresh.status_code == status.HTTP_401_UNAUTHORIZED


def test_api_login_incorrect_credentials():
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "password"},
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED


# ==========================================
# 4. DECORATORS & DEPENDENCY RBAC TESTS
# ==========================================


def test_rbac_decorators():
    # Setup test service method using decorator
    @require_permission("flag:create")
    async def create_flag_service(*, current_user: User):
        return "flag_created"

    async def test():
        # 1. Register admin user
        async with TestSessionLocal() as db1:
            uow1 = SQLAlchemyUnitOfWork(db1)
            reg_use_case = RegisterUserUseCase(uow1)
            user = await reg_use_case.execute("admin@test.com", "pass")

        # 2. Add roles/permissions in separate session
        async with TestSessionLocal() as db2:
            db_user = await db2.get(User, user.id)
            assert db_user is not None
            role = Role(name="Admin")
            permission = Permission(action="flag:create")
            role.permissions.append(permission)
            db_user.roles.append(role)
            db2.add_all([role, permission])
            await db2.commit()

        # 3. Create viewer user without permissions
        async with TestSessionLocal() as db3:
            uow3 = SQLAlchemyUnitOfWork(db3)
            reg_use_case3 = RegisterUserUseCase(uow3)
            user_no_perm = await reg_use_case3.execute("viewer@test.com", "pass")

        # 4. Fetch users with eager loaded relations
        async with TestSessionLocal() as db4:
            stmt = (
                select(User)
                .where(User.id == user.id)
                .options(selectinload(User.roles).selectinload(Role.permissions))
            )
            result = await db4.execute(stmt)
            eager_user = result.scalars().first()

            stmt_no_perm = (
                select(User)
                .where(User.id == user_no_perm.id)
                .options(selectinload(User.roles).selectinload(Role.permissions))
            )
            result_no_perm = await db4.execute(stmt_no_perm)
            eager_user_no_perm = result_no_perm.scalars().first()

            # Execute decorated service successfully
            res = await create_flag_service(current_user=eager_user)
            assert res == "flag_created"

            # Expect HTTP 403 Forbidden
            with pytest.raises(HTTPException) as exc_info:
                await create_flag_service(current_user=eager_user_no_perm)
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    asyncio.run(test())


def test_fastapi_dependency_rbac():
    # Register and setup permissions for a user
    async def setup_users():
        # 1. Register admin
        async with TestSessionLocal() as db1:
            uow1 = SQLAlchemyUnitOfWork(db1)
            reg_use_case = RegisterUserUseCase(uow1)
            admin = await reg_use_case.execute("auth_admin@test.com", "pass")

        # 2. Register viewer
        async with TestSessionLocal() as db2:
            uow2 = SQLAlchemyUnitOfWork(db2)
            reg_use_case2 = RegisterUserUseCase(uow2)
            viewer = await reg_use_case2.execute("auth_viewer@test.com", "pass")

        # 3. Associate permissions with admin
        async with TestSessionLocal() as db3:
            db_admin = await db3.get(User, admin.id)
            assert db_admin is not None
            admin_role = Role(name="SuperAdmin")
            perm = Permission(action="flag:create")
            admin_role.permissions.append(perm)
            db_admin.roles.append(admin_role)

            db3.add_all([admin_role, perm])
            await db3.commit()

        return admin.id, viewer.id

    admin_id, viewer_id = asyncio.run(setup_users())

    # Generate tokens
    admin_token = create_access_token(data={"sub": str(admin_id)})
    viewer_token = create_access_token(data={"sub": str(viewer_id)})

    # Request route with Admin Token -> Success
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    response_admin = client.get("/test-protected-route", headers=headers_admin)
    assert response_admin.status_code == status.HTTP_200_OK
    assert response_admin.json()["email"] == "auth_admin@test.com"

    # Request route with Viewer Token -> Forbidden
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}
    response_viewer = client.get("/test-protected-route", headers=headers_viewer)
    assert response_viewer.status_code == status.HTTP_403_FORBIDDEN

    # Request route with No Token -> Unauthorized
    response_anon = client.get("/test-protected-route")
    assert response_anon.status_code == status.HTTP_401_UNAUTHORIZED
