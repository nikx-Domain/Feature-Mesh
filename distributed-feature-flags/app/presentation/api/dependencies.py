import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db
from app.infrastructure.db.models import Role, User, Organization, UserOrganization


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to fetch the currently authenticated user from the database.
    Eagerly loads roles and permissions to avoid greenlet lazy loading errors.
    """
    user_payload = getattr(request.state, "user", None)
    if not user_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = user_payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: Missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: Invalid sub format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_permissions(*permissions: str) -> Callable[..., Any]:
    """
    FastAPI dependency factory that returns a dependency enforcing specific permissions.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = {
            perm.action for role in current_user.roles for perm in role.permissions
        }

        for permission in permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Missing required permission '{permission}'",
                )
        return current_user

    return dependency


async def get_current_tenant(
    request: Request,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    Dependency to resolve the active tenant (Organization) from request headers
    and verify the authenticated user has a membership inside it.
    """
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-ID header format: Must be a UUID",
        )

    membership = None
    for m in current_user.memberships:
        if m.organization_id == tenant_id:
            membership = m
            break

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Access denied to organization",
        )

    stmt = select(Organization).where(
        Organization.id == tenant_id, Organization.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    tenant = result.scalars().first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    request.state.membership_role = membership.role
    return tenant


def require_org_roles(*roles: str) -> Callable[..., Any]:
    """
    Dependency factory to restrict access based on organization membership roles.
    """

    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        tenant: Organization = Depends(get_current_tenant),
    ) -> UserOrganization:
        active_role = getattr(request.state, "membership_role", None)

        if not active_role or active_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient organization privileges",
            )

        for m in current_user.memberships:
            if m.organization_id == tenant.id:
                return m

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User organization membership not found",
        )

    return dependency
