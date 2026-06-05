import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.create_environment import CreateEnvironmentUseCase
from app.application.use_cases.create_organization import CreateOrganizationUseCase
from app.application.use_cases.create_project import CreateProjectUseCase
from app.core.dependencies import get_db, get_uow
from app.infrastructure.db.models import Environment, Organization, OrgRole, Project, User, UserOrganization
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.presentation.api.dependencies import get_current_tenant, get_current_user, require_org_roles

router = APIRouter(prefix="/tenancy", tags=["Tenancy"])


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime.datetime


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    created_at: datetime.datetime


class EnvironmentCreate(BaseModel):
    name: str


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime.datetime


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    body: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Create a new organization and assign the creator as the Owner."""
    use_case = CreateOrganizationUseCase(uow)
    org = await use_case.execute(body.name, current_user)
    return org


@router.get(
    "/organizations",
    response_model=list[OrganizationResponse],
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations of which the current user is a member."""
    stmt = (
        select(Organization)
        .join(UserOrganization)
        .where(
            UserOrganization.user_id == current_user.id,
            Organization.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    organizations = result.scalars().all()
    return organizations


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def create_project(
    body: ProjectCreate,
    tenant: Organization = Depends(get_current_tenant),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Create a new project in the active organization. Requires Owner or Admin role."""
    use_case = CreateProjectUseCase(uow)
    project = await use_case.execute(body.name, tenant.id)
    return project


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
)
async def list_projects(
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all projects in the active organization."""
    stmt = select(Project).where(
        Project.organization_id == tenant.id,
        Project.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return projects


@router.post(
    "/projects/{project_id}/environments",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def create_environment(
    project_id: uuid.UUID,
    body: EnvironmentCreate,
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Create a new environment inside a project. Requires project ownership verification and Owner/Admin role."""
    # Verify project exists and belongs to active tenant
    project_stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == tenant.id,
        Project.deleted_at.is_(None),
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    use_case = CreateEnvironmentUseCase(uow)
    env = await use_case.execute(body.name, project_id)
    return env


@router.get(
    "/projects/{project_id}/environments",
    response_model=list[EnvironmentResponse],
)
async def list_environments(
    project_id: uuid.UUID,
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List environments for a project inside the active organization."""
    # Verify project exists and belongs to active tenant
    project_stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == tenant.id,
        Project.deleted_at.is_(None),
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    stmt = select(Environment).where(
        Environment.project_id == project_id,
        Environment.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    environments = result.scalars().all()
    return environments
