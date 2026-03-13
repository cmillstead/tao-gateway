import logging
from typing import Any

import structlog
from structlog.types import EventDict

_SENSITIVE_PATTERNS = [
    "api_key",
    "token",
    "password",
    "secret",
    "coldkey",
    "hotkey",
    "authorization",
    "cookie",
]


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(pattern in lower for pattern in _SENSITIVE_PATTERNS)


def _redact_value(value: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive values in nested structures."""
    if depth > 5:
        return value
    if isinstance(value, dict):
        return {
            k: ("****" if _is_sensitive_key(k) else _redact_value(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, depth + 1) for item in value]
    return value


def _redact_sensitive_keys(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive values from structured log entries."""
    for key in list(event_dict.keys()):
        if _is_sensitive_key(key):
            event_dict[key] = "****"
        elif isinstance(event_dict[key], (dict, list)):
            event_dict[key] = _redact_value(event_dict[key])
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
