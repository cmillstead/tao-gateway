"""Fire-and-forget usage record writer.

Provides an async function that writes a UsageRecord to the database
without blocking the request path. Designed to be called via
asyncio.create_task() from subnet endpoint handlers.

When debug_mode is True, also writes request/response content to
the debug_logs table for developer troubleshooting (48h TTL).
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003
from typing import TYPE_CHECKING

import structlog

from gateway.core.logging import redact_string_value
from gateway.models.debug_log import DebugLog
from gateway.models.usage_record import UsageRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()

# Maximum size for debug content bodies (64KB)
MAX_DEBUG_CONTENT_SIZE = 65_536


def _truncate_content(content: str | None) -> str | None:
    """Redact sensitive patterns and truncate content."""
    if content is None:
        return None
    # Redact embedded credentials/tokens before storage (SEC-011)
    content = redact_string_value(content)
    if len(content) <= MAX_DEBUG_CONTENT_SIZE:
        return content
    logger.warning(
        "debug_content_truncated",
        original_size=len(content),
        max_size=MAX_DEBUG_CONTENT_SIZE,
    )
    return content[:MAX_DEBUG_CONTENT_SIZE] + "\n... [truncated at 64KB]"


async def record_usage(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    api_key_id: uuid.UUID,
    org_id: uuid.UUID,
    subnet_name: str,
    netuid: int,
    endpoint: str,
    miner_uid: str | None,
    latency_ms: int,
    status_code: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    debug_mode: bool = False,
    request_body: str | None = None,
    response_body: str | None = None,
) -> None:
    """Write a usage record to the database.

    Must be called via asyncio.create_task() to avoid blocking the response.
    Uses its own session to avoid transaction conflicts with the request session.

    When debug_mode is True and content is provided, also creates a DebugLog
    entry linked to the usage record.
    """
    try:
        async with session_factory() as session:
            record = UsageRecord(
                api_key_id=api_key_id,
                org_id=org_id,
                subnet_name=subnet_name,
                netuid=netuid,
                endpoint=endpoint,
                miner_uid=miner_uid,
                latency_ms=latency_ms,
                status_code=status_code,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            session.add(record)
            await session.flush()  # Get record.id for debug_log FK

            if debug_mode and (request_body is not None or response_body is not None):
                debug_log = DebugLog(
                    usage_record_id=record.id,
                    api_key_id=api_key_id,
                    request_body=_truncate_content(request_body),
                    response_body=_truncate_content(response_body),
                )
                session.add(debug_log)

            await session.commit()
    except Exception:
        logger.warning(
            "usage_record_write_failed",
            api_key_id=str(api_key_id),
            subnet=subnet_name,
            exc_info=True,
        )


def safe_json_dumps(data: dict[str, object] | None) -> str | None:
    """Safely serialize data to JSON string for debug logging."""
    if data is None:
        return None
    try:
        return json.dumps(data, default=str)
    except Exception:
        return None
