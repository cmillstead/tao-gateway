from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gateway.models.miner_score import MinerScore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from gateway.routing.scorer import MinerScorer

logger = structlog.get_logger()


class ScoreFlushTask:
    """Background task that periodically flushes in-memory miner scores to the database.

    Follows the MetagraphManager lifecycle pattern: start() / stop().
    """

    def __init__(
        self,
        scorer: MinerScorer,
        session_factory: async_sessionmaker[AsyncSession],
        flush_interval: int = 60,
        retention_days: int = 30,
    ) -> None:
        self._scorer = scorer
        self._session_factory = session_factory
        self._flush_interval = flush_interval
        self._retention_days = retention_days
        self._flush_task: asyncio.Task[None] | None = None

    async def flush_once(self) -> None:
        """Flush current scores to DB and clean up old entries."""
        snapshot = self._scorer.get_snapshot_and_reset()

        async with self._session_factory() as session:
            # Upsert scores using PostgreSQL ON CONFLICT
            for score_data in snapshot:
                if score_data.total_requests == 0:
                    continue  # No new observations since last flush

                stmt = pg_insert(MinerScore).values(
                    miner_uid=score_data.miner_uid,
                    hotkey=score_data.hotkey,
                    netuid=score_data.netuid,
                    quality_score=score_data.quality_score,
                    total_requests=score_data.total_requests,
                    successful_requests=score_data.successful_requests,
                    avg_latency_ms=score_data.avg_latency_ms,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_miner_scores_hotkey_netuid",
                    set_={
                        "quality_score": stmt.excluded.quality_score,
                        "total_requests": (
                            MinerScore.total_requests + stmt.excluded.total_requests
                        ),
                        "successful_requests": (
                            MinerScore.successful_requests
                            + stmt.excluded.successful_requests
                        ),
                        "avg_latency_ms": stmt.excluded.avg_latency_ms,
                        "updated_at": datetime.now(UTC),
                    },
                )
                await session.execute(stmt)

            # Cleanup old scores
            cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
            await session.execute(
                delete(MinerScore).where(MinerScore.updated_at < cutoff)
            )

            await session.commit()

        if snapshot:
            flushed_count = sum(1 for s in snapshot if s.total_requests > 0)
            if flushed_count > 0:
                logger.info(
                    "score_flush_complete",
                    flushed_miners=flushed_count,
                )

    async def _flush_loop(self) -> None:
        """Background loop that flushes periodically."""
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush_once()
            except Exception:
                logger.error("score_flush_failed", exc_info=True)

    async def start(self) -> None:
        """Start the background flush loop."""
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "score_flush_started",
            flush_interval=self._flush_interval,
            retention_days=self._retention_days,
        )

    async def stop(self) -> None:
        """Cancel the flush task and do a final flush."""
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        try:
            await self.flush_once()
        except Exception:
            logger.warning("score_flush_final_failed", exc_info=True)
        logger.info("score_flush_stopped")
