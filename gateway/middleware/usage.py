"""Fire-and-forget usage record writer.

Provides an async function that writes a UsageRecord to the database
without blocking the request path. Designed to be called via
asyncio.create_task() from subnet endpoint handlers.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

import structlog

from gateway.models.usage_record import UsageRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


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
) -> None:
    """Write a usage record to the database.

    Must be called via asyncio.create_task() to avoid blocking the response.
    Uses its own session to avoid transaction conflicts with the request session.
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
            await session.commit()
    except Exception:
        logger.warning(
            "usage_record_write_failed",
            api_key_id=str(api_key_id),
            subnet=subnet_name,
            exc_info=True,
        )
