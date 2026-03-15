import logging
import re
from typing import Any

import structlog
from structlog.types import EventDict

_SENSITIVE_PATTERNS = [
    "api_key",
    "auth_token",
    "bearer_token",
    "session_token",
    "password",
    "secret",
    "coldkey",
    "hotkey",
    "authorization",
    "cookie",
    "email",
    "database_url",
    "redis_url",
    "dsn",
    "connection_string",
    "wallet_path",
    "client_ip",
    # Story 3.3: additional patterns for Bittensor SDK edge cases
    "mnemonic",
    "seed_phrase",
    "private_key",
    "access_token",
    "refresh_token",
]

# Value-based redaction patterns: match sensitive data embedded in string values.
# These catch cases where a non-sensitive key (e.g., "error") contains a credential.
_API_KEY_RE = re.compile(r"tao_sk_(live|test)_\S+")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
# Match DB/Redis URLs with credentials (user:password@host pattern)
_CRED_URL_RE = re.compile(
    r"((?:postgresql|postgres|redis|mysql|amqp|mongodb)(?:\+\w+)?://)([^:]+):([^@]+)@"
)


_SENSITIVE_KEY_RE = re.compile(
    "|".join(re.escape(p) for p in _SENSITIVE_PATTERNS)
)


def _is_sensitive_key(key: str) -> bool:
    return _SENSITIVE_KEY_RE.search(key.lower()) is not None


def redact_string_value(value: str) -> str:
    """Redact sensitive patterns embedded in string values."""
    result = _API_KEY_RE.sub("tao_sk_****", value)
    result = _JWT_RE.sub("[REDACTED_JWT]", result)
    # Replace credentials in URLs: keep scheme + user, mask password
    result = _CRED_URL_RE.sub(r"\1\2:****@", result)
    return result


def _redact_value(value: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive values in nested structures."""
    # Strings are leaf nodes — always redact regardless of depth.
    if isinstance(value, str):
        return redact_string_value(value)
    if depth > 10:
        return value
    if isinstance(value, dict):
        return {
            k: ("****" if _is_sensitive_key(k) else _redact_value(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, depth + 1) for item in value]
    return value


_SAFE_KEYS = frozenset({"event", "level", "timestamp"})


def _redact_sensitive_keys(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive values from structured log entries."""
    for key in list(event_dict.keys()):
        if key in _SAFE_KEYS:
            continue
        if _is_sensitive_key(key):
            event_dict[key] = "****"
        elif isinstance(event_dict[key], (dict, list)):
            event_dict[key] = _redact_value(event_dict[key])
        elif isinstance(event_dict[key], str):
            event_dict[key] = redact_string_value(event_dict[key])
    return event_dict


def setup_logging() -> None:
    from gateway.core.config import settings

    use_json = settings.log_format == "json"

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    # format_exc_info is only needed for JSONRenderer;
    # ConsoleRenderer handles exception formatting itself.
    if use_json:
        processors.append(structlog.processors.format_exc_info)
    processors.append(_redact_sensitive_keys)
    processors.append(
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
