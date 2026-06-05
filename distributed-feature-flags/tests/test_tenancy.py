import asyncio
import datetime
import uuid

import pytest
from fastapi import Depends, status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.use_cases.create_environment import CreateEnvironmentUseCase
from app.application.use_cases.create_organization import CreateOrganizationUseCase
from app.application.use_cases.create_project import CreateProjectUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.core.database import Base
from app.core.dependencies import get_db, get_uow
from app.core.security import create_access_token
from app.infrastructure.db.models import Environment, Organization, OrgRole, Project, User, UserOrganization
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.main import app

# Setup in-memory SQLite for testing tenancy
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
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
            await session.commit()

    asyncio.run(clean())


# ==========================================
# 1. USE CASE TESTS
# ==========================================


def test_create_organization_use_case():
    async def test():
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)
            reg_user_uc = RegisterUserUseCase(uow)
            user = await reg_user_uc.execute("owner@test.com", "password")

            # Create organization
            create_org_uc = CreateOrganizationUseCase(uow)
            org = await create_org_uc.execute("My Organization", user)

            assert org.name == "My Organization"
            assert org.id is not None
            org_id = org.id
            user_id = user.id

        # Verify default membership is set to OWNER in a new session
        async with TestSessionLocal() as db2:
            stmt = select(UserOrganization).where(
                UserOrganization.user_id == user_id,
                UserOrganization.organization_id == org_id,
            )
            result = await db2.execute(stmt)
            membership = result.scalars().first()
            assert membership is not None
            assert membership.role == OrgRole.OWNER

    asyncio.run(test())


def test_create_project_use_case():
    async def test():
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)
            reg_user_uc = RegisterUserUseCase(uow)
            user = await reg_user_uc.execute("owner@test.com", "password")
            create_org_uc = CreateOrganizationUseCase(uow)
            org = await create_org_uc.execute("My Org", user)
            org_id = org.id

        async with TestSessionLocal() as db2:
            uow2 = SQLAlchemyUnitOfWork(db2)
            create_proj_uc = CreateProjectUseCase(uow2)
            proj = await create_proj_uc.execute("Project A", org_id)
            assert proj.name == "Project A"
            assert proj.organization_id == org_id

        async with TestSessionLocal() as db3:
            uow3 = SQLAlchemyUnitOfWork(db3)
            create_proj_uc2 = CreateProjectUseCase(uow3)
            # Verify uniqueness check in the same organization
            with pytest.raises(Exception):
                await create_proj_uc2.execute("Project A", org_id)

    asyncio.run(test())


def test_create_environment_use_case():
    async def test():
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)
            reg_user_uc = RegisterUserUseCase(uow)
            user = await reg_user_uc.execute("owner@test.com", "password")
            create_org_uc = CreateOrganizationUseCase(uow)
            org = await create_org_uc.execute("My Org", user)
            org_id = org.id

        async with TestSessionLocal() as db2:
            uow2 = SQLAlchemyUnitOfWork(db2)
            create_proj_uc = CreateProjectUseCase(uow2)
            proj = await create_proj_uc.execute("Project A", org_id)
            proj_id = proj.id

        async with TestSessionLocal() as db3:
            uow3 = SQLAlchemyUnitOfWork(db3)
            create_env_uc = CreateEnvironmentUseCase(uow3)
            env = await create_env_uc.execute("Production", proj_id)
            assert env.name == "Production"
            assert env.project_id == proj_id

        async with TestSessionLocal() as db4:
            uow4 = SQLAlchemyUnitOfWork(db4)
            create_env_uc2 = CreateEnvironmentUseCase(uow4)
            # Verify uniqueness check in the same project
            with pytest.raises(Exception):
                await create_env_uc2.execute("Production", proj_id)

    asyncio.run(test())


# ==========================================
# 2. ENDPOINT API TESTS
# ==========================================


def test_organization_endpoints_e2e():
    # 1. Register user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": "org_user@test.com", "password": "password123"},
    )
    assert reg_res.status_code == status.HTTP_201_CREATED
    user_id = reg_res.json()["id"]

    token = create_access_token({"sub": user_id})
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Organization
    create_res = client.post(
        "/api/v1/tenancy/organizations",
        json={"name": "Org 1"},
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    org_data = create_res.json()
    assert org_data["name"] == "Org 1"
    org_id = org_data["id"]

    # 3. List Organizations
    list_res = client.get(
        "/api/v1/tenancy/organizations",
        headers=headers,
    )
    assert list_res.status_code == status.HTTP_200_OK
    orgs = list_res.json()
    assert len(orgs) == 1
    assert orgs[0]["id"] == org_id


def test_project_endpoints_e2e_and_rbac():
    # Register Owner
    owner_res = client.post(
        "/api/v1/auth/register",
        json={"email": "owner_user@test.com", "password": "password123"},
    )
    owner_id = owner_res.json()["id"]
    owner_token = create_access_token({"sub": owner_id})

    # Register Member
    member_res = client.post(
        "/api/v1/auth/register",
        json={"email": "member_user@test.com", "password": "password123"},
    )
    member_id = member_res.json()["id"]
    member_token = create_access_token({"sub": member_id})

    # Register External User (not in org)
    external_res = client.post(
        "/api/v1/auth/register",
        json={"email": "external_user@test.com", "password": "password123"},
    )
    external_id = external_res.json()["id"]
    external_token = create_access_token({"sub": external_id})

    # Owner creates organization
    create_org_res = client.post(
        "/api/v1/tenancy/organizations",
        json={"name": "Org RBAC"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    org_id = create_org_res.json()["id"]

    # Add the member to the organization as OrgRole.MEMBER
    async def add_member():
        async with TestSessionLocal() as session:
            membership = UserOrganization(
                user_id=uuid.UUID(member_id),
                organization_id=uuid.UUID(org_id),
                role=OrgRole.MEMBER,
            )
            session.add(membership)
            await session.commit()

    asyncio.run(add_member())

    # 1. External user tries to access Org RBAC -> 403 Forbidden
    headers_ext = {"Authorization": f"Bearer {external_token}", "X-Tenant-ID": org_id}
    res = client.post("/api/v1/tenancy/projects", json={"name": "Proj Ext"}, headers=headers_ext)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 2. Member tries to create project -> 403 Forbidden (requires Owner/Admin)
    headers_member = {"Authorization": f"Bearer {member_token}", "X-Tenant-ID": org_id}
    res = client.post("/api/v1/tenancy/projects", json={"name": "Proj Mem"}, headers=headers_member)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 3. Owner creates project -> 201 Created
    headers_owner = {"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_id}
    res = client.post("/api/v1/tenancy/projects", json={"name": "Project Alpha"}, headers=headers_owner)
    assert res.status_code == status.HTTP_201_CREATED
    proj_id = res.json()["id"]

    # 4. Member lists projects -> 200 OK and sees Project Alpha
    res = client.get("/api/v1/tenancy/projects", headers=headers_member)
    assert res.status_code == status.HTTP_200_OK
    projs = res.json()
    assert len(projs) == 1
    assert projs[0]["id"] == proj_id

    # 5. External user lists projects -> 403 Forbidden
    res = client.get("/api/v1/tenancy/projects", headers=headers_ext)
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_environment_endpoints_e2e_and_isolation():
    # Register Owner
    owner_res = client.post(
        "/api/v1/auth/register",
        json={"email": "owner_user_env@test.com", "password": "password123"},
    )
    owner_id = owner_res.json()["id"]
    owner_token = create_access_token({"sub": owner_id})

    # Owner creates Organization A
    org_a_res = client.post(
        "/api/v1/tenancy/organizations",
        json={"name": "Org A"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    org_a_id = org_a_res.json()["id"]

    # Owner creates Organization B
    org_b_res = client.post(
        "/api/v1/tenancy/organizations",
        json={"name": "Org B"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    org_b_id = org_b_res.json()["id"]

    # Owner creates Project A in Organization A
    res = client.post(
        "/api/v1/tenancy/projects",
        json={"name": "Project A"},
        headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_a_id},
    )
    proj_a_id = res.json()["id"]

    # Owner creates Project B in Organization B
    res = client.post(
        "/api/v1/tenancy/projects",
        json={"name": "Project B"},
        headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_b_id},
    )
    proj_b_id = res.json()["id"]

    # 1. Create Environment in Project A using Org A context -> Success
    headers_org_a = {"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_a_id}
    res = client.post(
        f"/api/v1/tenancy/projects/{proj_a_id}/environments",
        json={"name": "Production"},
        headers=headers_org_a,
    )
    assert res.status_code == status.HTTP_201_CREATED
    env_id = res.json()["id"]

    # 2. Try to create Environment in Project A using Org B context -> 404 Not Found (Cross-tenant breach prevented)
    headers_org_b = {"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_b_id}
    res = client.post(
        f"/api/v1/tenancy/projects/{proj_a_id}/environments",
        json={"name": "Staging"},
        headers=headers_org_b,
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # 3. List Environments of Project A using Org A context -> 200 OK and lists 1 environment
    res = client.get(
        f"/api/v1/tenancy/projects/{proj_a_id}/environments",
        headers=headers_org_a,
    )
    assert res.status_code == status.HTTP_200_OK
    envs = res.json()
    assert len(envs) == 1
    assert envs[0]["id"] == env_id

    # 4. List Environments of Project A using Org B context -> 404 Not Found
    res = client.get(
        f"/api/v1/tenancy/projects/{proj_a_id}/environments",
        headers=headers_org_b,
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_soft_delete_unique_indexes_and_name_reuse():
    async def test():
        # First session: Create project
        async with TestSessionLocal() as db:
            uow = SQLAlchemyUnitOfWork(db)
            reg_user_uc = RegisterUserUseCase(uow)
            user = await reg_user_uc.execute("soft_delete@test.com", "password")

            create_org_uc = CreateOrganizationUseCase(uow)
            org = await create_org_uc.execute("My Org SD", user)
            org_id = org.id

            create_proj_uc = CreateProjectUseCase(uow)
            proj1 = await create_proj_uc.execute("Project A", org_id)
            proj1_id = proj1.id

        # Second session: Soft-delete the project
        async with TestSessionLocal() as db2:
            # Re-fetch project to update it
            proj1_fetched = await db2.get(Project, proj1_id)
            proj1_fetched.deleted_at = datetime.datetime.now(datetime.timezone.utc)
            await db2.commit()

        # Third session: Create new project with same name -> Should succeed
        async with TestSessionLocal() as db3:
            uow3 = SQLAlchemyUnitOfWork(db3)
            create_proj_uc3 = CreateProjectUseCase(uow3)
            proj2 = await create_proj_uc3.execute("Project A", org_id)
            assert proj2.id != proj1_id

        # Fourth session: Creating a third project with same name -> Should fail (since second is active)
        async with TestSessionLocal() as db4:
            uow4 = SQLAlchemyUnitOfWork(db4)
            create_proj_uc4 = CreateProjectUseCase(uow4)
            with pytest.raises(Exception):
                await create_proj_uc4.execute("Project A", org_id)

    asyncio.run(test())
