from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from gateway.core.database import get_session_factory
from gateway.models.miner_score import MinerScore
from gateway.routing.scorer import MinerScorer, ScoreObservation
from gateway.tasks.score_flush import ScoreFlushTask


def _make_observation(
    miner_uid: int = 1,
    hotkey: str = "abc12345",
    netuid: int = 1,
) -> ScoreObservation:
    return ScoreObservation(
        miner_uid=miner_uid,
        hotkey=hotkey,
        netuid=netuid,
        success=True,
        latency_ms=100.0,
        response_valid=True,
        response_complete=True,
        timestamp=datetime.now(UTC),
    )


class TestScoreFlushTask:
    async def test_flush_writes_scores_to_db(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))
        scorer.record_observation(_make_observation(miner_uid=2, hotkey="bbb"))

        session_factory = get_session_factory()
        task = ScoreFlushTask(
            scorer=scorer,
            session_factory=session_factory,
            flush_interval=60,
            retention_days=30,
        )

        await task.flush_once()

        async with session_factory() as session:
            result = await session.execute(select(MinerScore))
            rows = result.scalars().all()
        assert len(rows) == 2
        hotkeys = {r.hotkey for r in rows}
        assert hotkeys == {"aaa", "bbb"}

    async def test_flush_upserts_existing_scores(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))

        session_factory = get_session_factory()
        task = ScoreFlushTask(
            scorer=scorer,
            session_factory=session_factory,
            flush_interval=60,
            retention_days=30,
        )

        await task.flush_once()

        # Record more observations and flush again
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))
        await task.flush_once()

        async with session_factory() as session:
            result = await session.execute(select(MinerScore))
            rows = result.scalars().all()
        # Should still be 1 row (upserted, not duplicated)
        assert len(rows) == 1

    async def test_cleanup_deletes_old_scores(self) -> None:
        session_factory = get_session_factory()
        scorer = MinerScorer(ema_alpha=0.3)

        # Manually insert an old score
        async with session_factory() as session:
            old_score = MinerScore(
                miner_uid=99,
                hotkey="old_miner",
                netuid=1,
                quality_score=0.5,
                total_requests=10,
                successful_requests=5,
                avg_latency_ms=200.0,
            )
            session.add(old_score)
            await session.commit()

            # Manually set updated_at to 31 days ago
            old_score.updated_at = datetime.now(UTC) - timedelta(days=31)
            await session.commit()

        task = ScoreFlushTask(
            scorer=scorer,
            session_factory=session_factory,
            flush_interval=60,
            retention_days=30,
        )

        await task.flush_once()

        async with session_factory() as session:
            result = await session.execute(
                select(MinerScore).where(MinerScore.hotkey == "old_miner")
            )
            assert result.scalar_one_or_none() is None

    async def test_flush_with_empty_scores(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        session_factory = get_session_factory()
        task = ScoreFlushTask(
            scorer=scorer,
            session_factory=session_factory,
            flush_interval=60,
            retention_days=30,
        )

        # Should not raise
        await task.flush_once()

        async with session_factory() as session:
            result = await session.execute(select(MinerScore))
            assert len(result.scalars().all()) == 0

    async def test_start_stop_lifecycle(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        session_factory = get_session_factory()
        task = ScoreFlushTask(
            scorer=scorer,
            session_factory=session_factory,
            flush_interval=1,  # 1 second for fast test
            retention_days=30,
        )

        await task.start()
        assert task._flush_task is not None
        assert not task._flush_task.done()

        await task.stop()
        assert task._flush_task.done() or task._flush_task.cancelled()
