"""Tests for usage aggregation background task."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from gateway.core.database import get_session_factory
from gateway.models.api_key import ApiKey
from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord
from gateway.tasks.usage_aggregation import UsageAggregationTask


@pytest.fixture
async def org_and_key() -> tuple[uuid.UUID, uuid.UUID]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="agg-test@example.com", password_hash="fakehash")
        session.add(org)
        await session.flush()
        key = ApiKey(org_id=org.id, prefix="tao_sk_test_agg", key_hash="fakekeyhash")
        session.add(key)
        await session.commit()
        return org.id, key.id


@pytest.fixture
async def seeded_records(
    org_and_key: tuple[uuid.UUID, uuid.UUID],
) -> tuple[uuid.UUID, uuid.UUID, datetime]:
    """Seed usage records for yesterday."""
    org_id, key_id = org_and_key
    yesterday = datetime.now(UTC) - timedelta(days=1)
    yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Create 10 records with known latencies for percentile testing
        latencies = [50, 80, 100, 120, 150, 180, 200, 250, 300, 500]
        for i, lat in enumerate(latencies):
            session.add(UsageRecord(
                api_key_id=key_id,
                org_id=org_id,
                subnet_name="sn1",
                netuid=1,
                endpoint="/v1/chat/completions",
                miner_uid=f"miner{i}",
                latency_ms=lat,
                status_code=200 if i < 8 else 502,
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                created_at=yesterday_start + timedelta(hours=i),
            ))
        await session.commit()

    return org_id, key_id, yesterday


@pytest.mark.asyncio
async def test_aggregate_day(seeded_records: tuple[uuid.UUID, uuid.UUID, datetime]) -> None:
    org_id, key_id, yesterday = seeded_records
    session_factory = get_session_factory()

    task = UsageAggregationTask(session_factory=session_factory)
    upserted = await task.aggregate_day(yesterday)
    assert upserted == 1  # One group: (org_id, key_id, 1, sn1, date)

    async with session_factory() as session:
        summary = await session.scalar(select(DailyUsageSummary))
        assert summary is not None
        assert summary.request_count == 10
        assert summary.success_count == 8
        assert summary.error_count == 2
        assert summary.total_prompt_tokens == 100  # 10 * 10
        assert summary.total_completion_tokens == 200  # 10 * 20
        # Verify percentiles are reasonable (exact values depend on PostgreSQL's interpolation)
        assert summary.p50_latency_ms > 0
        assert summary.p95_latency_ms >= summary.p50_latency_ms
        assert summary.p99_latency_ms >= summary.p95_latency_ms


@pytest.mark.asyncio
async def test_aggregate_day_idempotent(
    seeded_records: tuple[uuid.UUID, uuid.UUID, datetime],
) -> None:
    """Running aggregation twice produces the same result."""
    org_id, key_id, yesterday = seeded_records
    session_factory = get_session_factory()

    task = UsageAggregationTask(session_factory=session_factory)
    await task.aggregate_day(yesterday)
    await task.aggregate_day(yesterday)  # Second run

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(DailyUsageSummary)
        )
        assert count == 1  # Still just one summary row


@pytest.mark.asyncio
async def test_aggregate_day_no_records() -> None:
    """Aggregating a day with no records produces no summaries."""
    session_factory = get_session_factory()
    task = UsageAggregationTask(session_factory=session_factory)

    yesterday = datetime.now(UTC) - timedelta(days=1)
    upserted = await task.aggregate_day(yesterday)
    assert upserted == 0


@pytest.mark.asyncio
async def test_cleanup_old_records(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()

    # Create records: one old (100 days ago) and one recent (1 day ago)
    async with session_factory() as session:
        old_record = UsageRecord(
            api_key_id=key_id,
            org_id=org_id,
            subnet_name="sn1",
            netuid=1,
            endpoint="/v1/chat/completions",
            miner_uid="old",
            latency_ms=100,
            status_code=200,
            created_at=datetime.now(UTC) - timedelta(days=100),
        )
        recent_record = UsageRecord(
            api_key_id=key_id,
            org_id=org_id,
            subnet_name="sn1",
            netuid=1,
            endpoint="/v1/chat/completions",
            miner_uid="recent",
            latency_ms=100,
            status_code=200,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        session.add(old_record)
        session.add(recent_record)
        await session.commit()

    task = UsageAggregationTask(session_factory=session_factory, retention_days=90)
    deleted = await task.cleanup_old_records()
    assert deleted == 1

    async with session_factory() as session:
        remaining = await session.scalar(select(func.count()).select_from(UsageRecord))
        assert remaining == 1
