import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Match

from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    HTTP_ERRORS_TOTAL,
)

logger = structlog.get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        method = request.method
        
        # Get path without path parameters if possible to reduce cardinality
        # E.g. /projects/123 -> /projects/{project_id}
        # FastAPI resolves routes after some middleware, but we can try to find the route
        route_path = request.url.path
        for route in request.app.routes:
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                route_path = route.path
                break
                
        # Do not track metrics endpoint to avoid noise
        if route_path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            
            HTTP_REQUESTS_TOTAL.labels(
                method=method, 
                endpoint=route_path, 
                status_code=status_code
            ).inc()
            
            if response.status_code >= 500:
                HTTP_ERRORS_TOTAL.labels(
                    method=method, 
                    endpoint=route_path
                ).inc()
                
            return response

        except Exception as e:
            status_code = "500"
            HTTP_REQUESTS_TOTAL.labels(
                method=method, 
                endpoint=route_path, 
                status_code=status_code
            ).inc()
            HTTP_ERRORS_TOTAL.labels(
                method=method, 
                endpoint=route_path
            ).inc()
            
            logger.error("Unhandled exception during request processing", error=str(e), exc_info=True)
            raise e
            
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, 
                endpoint=route_path
            ).observe(duration)
