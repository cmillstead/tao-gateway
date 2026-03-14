from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.usage_record import UsageRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class UsageAggregationTask:
    """Background task that aggregates daily usage records into summaries.

    Follows the ScoreFlushTask lifecycle pattern: start() / stop().
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        aggregation_interval: int = 86400,
        retention_days: int = 90,
    ) -> None:
        self._session_factory = session_factory
        self._aggregation_interval = aggregation_interval
        self._retention_days = retention_days
        self._task: asyncio.Task[None] | None = None

    async def aggregate_day(self, target_date: datetime) -> int:
        """Aggregate usage records for a specific day into daily summaries.

        Returns the number of summary rows upserted.
        """
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        async with self._session_factory() as session:
            # Use raw SQL for percentile_cont which is cleaner than ORM
            query = text(  # noqa: E501
                """
SELECT org_id, api_key_id, netuid, subnet_name,
  DATE(created_at) as summary_date,
  COUNT(*) as request_count,
  COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 400) as success_count,
  COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
  COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0)::int as p50_latency_ms,
  COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int as p95_latency_ms,
  COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms), 0)::int as p99_latency_ms,
  COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
  COALESCE(SUM(completion_tokens), 0) as total_completion_tokens
FROM usage_records
WHERE created_at >= :start_of_day AND created_at < :end_of_day
GROUP BY org_id, api_key_id, netuid, subnet_name, DATE(created_at)
"""
            )
            rows = await session.execute(
                query,
                {"start_of_day": start_of_day, "end_of_day": end_of_day},
            )

            upserted = 0
            for row in rows:
                stmt = pg_insert(DailyUsageSummary).values(
                    org_id=row.org_id,
                    api_key_id=row.api_key_id,
                    netuid=row.netuid,
                    subnet_name=row.subnet_name,
                    summary_date=row.summary_date,
                    request_count=row.request_count,
                    success_count=row.success_count,
                    error_count=row.error_count,
                    p50_latency_ms=row.p50_latency_ms,
                    p95_latency_ms=row.p95_latency_ms,
                    p99_latency_ms=row.p99_latency_ms,
                    total_prompt_tokens=row.total_prompt_tokens,
                    total_completion_tokens=row.total_completion_tokens,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_daily_usage_summaries_key_subnet_date",
                    set_={
                        "request_count": stmt.excluded.request_count,
                        "success_count": stmt.excluded.success_count,
                        "error_count": stmt.excluded.error_count,
                        "p50_latency_ms": stmt.excluded.p50_latency_ms,
                        "p95_latency_ms": stmt.excluded.p95_latency_ms,
                        "p99_latency_ms": stmt.excluded.p99_latency_ms,
                        "total_prompt_tokens": stmt.excluded.total_prompt_tokens,
                        "total_completion_tokens": stmt.excluded.total_completion_tokens,
                    },
                )
                await session.execute(stmt)
                upserted += 1

            await session.commit()

        return upserted

    async def cleanup_old_records(self) -> int:
        """Delete usage records older than retention_days."""
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)

        async with self._session_factory() as session:
            result = await session.execute(
                delete(UsageRecord).where(UsageRecord.created_at < cutoff)
            )
            await session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    async def run_once(self) -> None:
        """Aggregate yesterday's records and clean up old data."""
        yesterday = datetime.now(UTC) - timedelta(days=1)

        upserted = await self.aggregate_day(yesterday)
        if upserted > 0:
            logger.info(
                "usage_aggregation_complete",
                target_date=yesterday.date().isoformat(),
                summaries_upserted=upserted,
            )

        deleted = await self.cleanup_old_records()
        if deleted > 0:
            logger.info(
                "usage_retention_cleanup",
                records_deleted=deleted,
                retention_days=self._retention_days,
            )

    async def _loop(self) -> None:
        """Background loop that runs aggregation periodically."""
        while True:
            await asyncio.sleep(self._aggregation_interval)
            try:
                await self.run_once()
            except Exception:
                logger.error("usage_aggregation_failed", exc_info=True)

    async def start(self) -> None:
        """Start the background aggregation loop."""
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "usage_aggregation_started",
            aggregation_interval=self._aggregation_interval,
            retention_days=self._retention_days,
        )

    async def stop(self) -> None:
        """Cancel the aggregation task and do a final run."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        try:
            await self.run_once()
        except Exception:
            logger.warning("usage_aggregation_final_failed", exc_info=True)
        logger.info("usage_aggregation_stopped")
