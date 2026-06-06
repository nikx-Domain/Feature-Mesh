import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Match

from app.observability.http_metrics import (
    http_request_duration_seconds,
    http_requests_total,
    http_errors_total,
)

logger = structlog.get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        
        # Clear contextvars and bind request_id/correlation_id for this async context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # We can also check for X-Correlation-ID from the client if needed, but for now we default to request_id
        correlation_id = request.headers.get("X-Correlation-ID", request_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        method = request.method
        
        # Attempt to get the matched route path to avoid high cardinality metrics
        # For example, we want '/projects/{project_id}' instead of '/projects/123e4567'
        route_path = request.url.path
        for route in request.app.routes:
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                route_path = route.path
                break
                
        # Exclude /metrics from observability tracking to prevent recursive noise
        if route_path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            
            http_requests_total.labels(
                method=method, 
                endpoint=route_path, 
                status_code=status_code
            ).inc()
            
            if response.status_code >= 500:
                http_errors_total.labels(
                    method=method, 
                    endpoint=route_path
                ).inc()
                
            return response

        except Exception as e:
            status_code = "500"
            http_requests_total.labels(
                method=method, 
                endpoint=route_path, 
                status_code=status_code
            ).inc()
            http_errors_total.labels(
                method=method, 
                endpoint=route_path
            ).inc()
            
            logger.error("Unhandled exception during request processing", error=str(e), exc_info=True)
            raise e
            
        finally:
            duration = time.perf_counter() - start_time
            http_request_duration_seconds.labels(
                method=method, 
                endpoint=route_path
            ).observe(duration)
