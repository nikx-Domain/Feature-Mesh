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

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Use ConsoleRenderer for human-friendly dev outputs, and JSONRenderer for production systems
            (
                structlog.processors.JSONRenderer()
                if settings.APP_ENV != "development"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
