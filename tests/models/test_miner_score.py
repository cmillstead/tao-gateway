import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from gateway.core.database import get_engine, get_session_factory
from gateway.models.miner_score import MinerScore


class TestMinerScoreModel:
    async def test_create_and_read(self) -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            score = MinerScore(
                miner_uid=1,
                hotkey="abc12345def67890",
                netuid=1,
                quality_score=0.85,
                total_requests=100,
                successful_requests=95,
                avg_latency_ms=150.0,
            )
            session.add(score)
            await session.commit()
            await session.refresh(score)

            assert score.id is not None
            assert score.miner_uid == 1
            assert score.hotkey == "abc12345def67890"
            assert score.netuid == 1
            assert score.quality_score == pytest.approx(0.85)
            assert score.total_requests == 100
            assert score.successful_requests == 95
            assert score.avg_latency_ms == pytest.approx(150.0)
            assert score.created_at is not None
            assert score.updated_at is not None

    async def test_unique_constraint_hotkey_netuid(self) -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            score1 = MinerScore(
                miner_uid=1, hotkey="same_hotkey", netuid=1,
                quality_score=0.5, total_requests=10, successful_requests=5,
                avg_latency_ms=100.0,
            )
            session.add(score1)
            await session.commit()

        async with session_factory() as session:
            score2 = MinerScore(
                miner_uid=1, hotkey="same_hotkey", netuid=1,
                quality_score=0.6, total_requests=20, successful_requests=15,
                avg_latency_ms=200.0,
            )
            session.add(score2)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_index_exists_netuid_quality_score(self) -> None:
        engine = get_engine()
        async with engine.connect() as conn:
            indexes = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_indexes("miner_scores")
            )
        index_names = [idx["name"] for idx in indexes]
        assert "ix_miner_scores_netuid_quality_score" in index_names
