# utils/logger.py
from __future__ import annotations
from typing import Any, Callable, Optional, Mapping
import os
import sys
import uuid
import time
import logging
from logging.handlers import RotatingFileHandler

import structlog

# ------------------------
# Configuration
# ------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_JSON = os.getenv("LOG_JSON", "true").lower() == "true"
MASK_FIELDS = {s.strip().lower() for s in os.getenv("LOG_MASK_FIELDS", "password,secret,token,authorization,api_key").split(",")}

# ------------------------
# Sensitive data masking
# ------------------------

def _mask_value(key: str, value: Any) -> Any:
    try:
        if key.lower() in MASK_FIELDS and isinstance(value, str):
            return "***masked***"
        return value
    except Exception:
        return value


def _mask_dict(d: Mapping[str, Any]) -> Mapping[str, Any]:
    return {k: _mask_value(k, v) for k, v in d.items()}


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        # Attach a correlation id if not present
        if not hasattr(record, "corr_id"):
            record.corr_id = str(uuid.uuid4())
        return True


def _get_handlers() -> list[logging.Handler]:
    handlers: list[logging.Handler] = []
    stream = logging.StreamHandler(sys.stdout)
    handlers.append(stream)
    # Optional rotation to file
    if LOG_FILE:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
        handlers.append(file_handler)
    return handlers


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Callable] = [
        structlog.contextvars.merge_contextvars,
        timestamper,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # mask last so we affect event dict
        lambda logger, method_name, event_dict: _mask_dict(event_dict),
    ]

    renderer: Callable
    if LOG_JSON:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, LOG_LEVEL, logging.INFO)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # stdlib root logger bridging
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), handlers=_get_handlers(), format="%(message)s")
    for h in logging.getLogger().handlers:
        h.addFilter(CorrelationIdFilter())


# Initialize on import for convenience in simple apps
configure_logging()
logger = structlog.get_logger()


# Performance decorator
from functools import wraps

def log_timing(name: Optional[str] = None):
    """Log execution time of a function. Usage: @log_timing("db.query")"""
    def deco(fn: Callable):
        label = name or fn.__name__
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                ms = (time.perf_counter() - start) * 1000.0
                logger.info("perf", op=label, ms=round(ms, 2))
        return wrapper
    return deco