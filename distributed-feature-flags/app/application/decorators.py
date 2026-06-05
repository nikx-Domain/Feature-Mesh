from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, status

from app.infrastructure.db.models import User


def require_permission(action: str):
    """
    Python decorator to enforce RBAC permissions on application services/functions.
    Expects 'current_user' (User object) to be passed as a keyword argument.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user: User | None = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required: No user context provided to service",
                )

            has_perm = False
            for role in current_user.roles:
                for perm in role.permissions:
                    if perm.action == action:
                        has_perm = True
                        break
                if has_perm:
                    break

            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Missing required permission '{action}'",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
