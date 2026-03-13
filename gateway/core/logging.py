import logging
from typing import Any

import structlog
from structlog.types import EventDict


def _redact_sensitive_keys(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive values from structured log entries."""
    sensitive_patterns = ["api_key", "token", "password", "secret", "coldkey", "hotkey"]
    for key in list(event_dict.keys()):
        if any(pattern in key.lower() for pattern in sensitive_patterns):
            event_dict[key] = "****"
    return event_dict


def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_sensitive_keys,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
