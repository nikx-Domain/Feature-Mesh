import logging
import sys

import structlog
import structlog.stdlib

from app.core.config import settings

def setup_logging():
    # Configure the standard logging library
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.LOG_LEVEL.upper()),
    )

    # Configure structlog for JSON logging, Request ID, Correlation ID, Error Context, Log Levels
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars, # Pulls request_id and correlation_id
            structlog.processors.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info, # Error context
            # Always use JSON in observability layer
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
