import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.archive_feature_flag import ArchiveFeatureFlagUseCase
from app.application.use_cases.create_feature_flag import CreateFeatureFlagUseCase
from app.application.use_cases.list_audit_events import ListAuditEventsUseCase
from app.application.use_cases.toggle_feature_flag import ToggleFeatureFlagUseCase
from app.application.use_cases.update_feature_flag import UpdateFeatureFlagUseCase
from app.core.dependencies import get_db, get_uow
from app.domain.entities import FlagType
from app.domain.exceptions import EntityNotFoundException
from app.infrastructure.db.models import (
    Environment,
    Organization,
    OrgRole,
    Project,
    User,
)
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from app.presentation.api.dependencies import (
    get_current_tenant,
    get_current_user,
    require_org_roles,
)

router = APIRouter(prefix="", tags=["Feature Flags"])


class FeatureFlagCreate(BaseModel):
    name: str
    key: str
    description: str | None = None
    type: FlagType = FlagType.BOOLEAN


class FeatureFlagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key: str
    description: str | None
    type: FlagType
    version: int
    is_archived: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ToggleFlagRequest(BaseModel):
    is_enabled: bool


class FeatureFlagEnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_flag_id: uuid.UUID
    environment_id: uuid.UUID
    is_enabled: bool
    version: int
    updated_at: datetime.datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    previous_state: dict[str, Any] | None
    new_state: dict[str, Any] | None
    created_at: datetime.datetime


async def verify_project_access(project_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession):
    stmt = select(Project).where(
        Project.id == project_id,
        Project.organization_id == tenant_id,
        Project.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise EntityNotFoundException("Project not found")

async def verify_environment_access(environment_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession):
    stmt = (
        select(Environment)
        .join(Project)
        .where(
            Environment.id == environment_id,
            Project.organization_id == tenant_id,
            Environment.deleted_at.is_(None),
            Project.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise EntityNotFoundException("Environment not found")


@router.post(
    "/projects/{project_id}/flags",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def create_feature_flag(
    project_id: uuid.UUID,
    body: FeatureFlagCreate,
    current_user: User = Depends(get_current_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Create a new feature flag. Requires Owner or Admin role."""
    await verify_project_access(project_id, tenant.id, db)
    use_case = CreateFeatureFlagUseCase(uow)
    flag = await use_case.execute(
        name=body.name,
        key=body.key,
        project_id=project_id,
        organization_id=tenant.id,
        user_id=current_user.id,
        description=body.description,
        flag_type=body.type,
    )
    return flag


@router.get(
    "/projects/{project_id}/flags",
    response_model=list[FeatureFlagResponse],
)
async def list_feature_flags(
    project_id: uuid.UUID,
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """List all feature flags in a project."""
    await verify_project_access(project_id, tenant.id, db)

    async with uow:
        flags = await uow.feature_flags.list_for_project(project_id)
        return list(flags)


@router.patch(
    "/projects/{project_id}/flags/{flag_id}",
    response_model=FeatureFlagResponse,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def update_feature_flag(
    project_id: uuid.UUID,
    flag_id: uuid.UUID,
    body: FeatureFlagUpdate,
    current_user: User = Depends(get_current_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Update basic properties of a feature flag."""
    await verify_project_access(project_id, tenant.id, db)
    use_case = UpdateFeatureFlagUseCase(uow)
    flag = await use_case.execute(
        flag_id=flag_id,
        organization_id=tenant.id,
        user_id=current_user.id,
        name=body.name,
        description=body.description,
    )
    return flag


@router.delete(
    "/projects/{project_id}/flags/{flag_id}",
    response_model=FeatureFlagResponse,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def archive_feature_flag(
    project_id: uuid.UUID,
    flag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Soft-delete (archive) a feature flag."""
    await verify_project_access(project_id, tenant.id, db)
    use_case = ArchiveFeatureFlagUseCase(uow)
    flag = await use_case.execute(
        flag_id=flag_id,
        organization_id=tenant.id,
        user_id=current_user.id,
    )
    return flag


@router.patch(
    "/environments/{environment_id}/flags/{flag_id}/toggle",
    response_model=FeatureFlagEnvironmentResponse,
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def toggle_feature_flag(
    environment_id: uuid.UUID,
    flag_id: uuid.UUID,
    body: ToggleFlagRequest,
    current_user: User = Depends(get_current_user),
    tenant: Organization = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """Enable or disable a feature flag in a specific environment."""
    await verify_environment_access(environment_id, tenant.id, db)
    use_case = ToggleFeatureFlagUseCase(uow)
    state = await use_case.execute(
        feature_flag_id=flag_id,
        environment_id=environment_id,
        organization_id=tenant.id,
        user_id=current_user.id,
        is_enabled=body.is_enabled,
    )
    return state


@router.get(
    "/audit-events",
    response_model=list[AuditEventResponse],
    dependencies=[Depends(require_org_roles(OrgRole.OWNER, OrgRole.ADMIN))],
)
async def list_audit_events(
    entity_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant: Organization = Depends(get_current_tenant),
    uow: SQLAlchemyUnitOfWork = Depends(get_uow),
):
    """List audit events. Can be filtered by entity to see version history."""
    use_case = ListAuditEventsUseCase(uow)
    events = await use_case.execute(
        organization_id=tenant.id,
        entity_id=entity_id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return list(events)
