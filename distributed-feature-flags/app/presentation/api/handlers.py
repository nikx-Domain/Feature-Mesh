from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AuthenticationException,
    DomainException,
    EntityAlreadyExistsException,
    EntityNotFoundException,
    PermissionDeniedException,
)


async def entity_not_found_handler(
    request: Request, exc: EntityNotFoundException
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message},
    )


async def entity_already_exists_handler(
    request: Request, exc: EntityAlreadyExistsException
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": exc.message},
    )


async def permission_denied_handler(
    request: Request, exc: PermissionDeniedException
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message},
    )


async def authentication_handler(
    request: Request, exc: AuthenticationException
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": exc.message},
    )


async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers with the FastAPI application."""
    app.add_exception_handler(EntityNotFoundException, entity_not_found_handler)
    app.add_exception_handler(
        EntityAlreadyExistsException, entity_already_exists_handler
    )
    app.add_exception_handler(PermissionDeniedException, permission_denied_handler)
    app.add_exception_handler(AuthenticationException, authentication_handler)
    app.add_exception_handler(DomainException, domain_exception_handler)
