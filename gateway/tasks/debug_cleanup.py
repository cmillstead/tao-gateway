from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete

from gateway.models.debug_log import DebugLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class DebugLogCleanupTask:
    """Background task that deletes debug log entries older than the retention period.

    Follows the ScoreFlushTask/UsageAggregationTask lifecycle pattern: start() / stop().
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cleanup_interval_seconds: int = 3600,
        retention_hours: int = 48,
    ) -> None:
        self._session_factory = session_factory
        self._cleanup_interval = cleanup_interval_seconds
        self._retention_hours = retention_hours
        self._task: asyncio.Task[None] | None = None

    async def cleanup_once(self) -> int:
        """Delete debug log entries older than retention_hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=self._retention_hours)

        async with self._session_factory() as session:
            result = await session.execute(
                delete(DebugLog).where(DebugLog.created_at < cutoff)
            )
            await session.commit()
            deleted = int(getattr(result, "rowcount", 0) or 0)

        if deleted > 0:
            logger.info(
                "debug_log_cleanup_complete",
                records_deleted=deleted,
                retention_hours=self._retention_hours,
            )

        return deleted

    async def _loop(self) -> None:
        """Background loop that runs cleanup periodically."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            try:
                await self.cleanup_once()
            except Exception:
                logger.error("debug_log_cleanup_failed", exc_info=True)

    async def start(self) -> None:
        """Start the background cleanup loop."""
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "debug_log_cleanup_started",
            cleanup_interval=self._cleanup_interval,
            retention_hours=self._retention_hours,
        )

    async def stop(self) -> None:
        """Cancel the cleanup task and do a final cleanup."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        try:
            await self.cleanup_once()
        except Exception:
            logger.warning("debug_log_cleanup_final_failed", exc_info=True)
        logger.info("debug_log_cleanup_stopped")
