from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_token


class JWTAuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that intercepts incoming HTTP requests, decodes any
    Bearer JWT token present in the Authorization header, and attaches
    the decoded payload to the request state context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        auth_header = request.headers.get("Authorization")
        request.state.user = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # Decode and validate. This validates signature and expiration.
                payload = decode_token(token)
                if payload.get("type") == "access":
                    request.state.user = payload
            except Exception:
                # Fail silently at middleware level to allow access to public routes (health, login)
                pass

        response = await call_next(request)
        return response
