"""Tests for usage service — queries and quota calculation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from gateway.core.database import get_session_factory
from gateway.models.api_key import ApiKey
from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.organization import Organization
from gateway.services.usage_service import get_quota_status, get_usage_summaries


@pytest.fixture
async def org_and_key() -> tuple[uuid.UUID, uuid.UUID]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="svc-test@example.com", password_hash="fakehash")
        session.add(org)
        await session.flush()
        key = ApiKey(org_id=org.id, prefix="tao_sk_test_svc", key_hash="fakekeyhash")
        session.add(key)
        await session.commit()
        return org.id, key.id


@pytest.fixture
async def seed_summaries(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed daily summaries for the last 3 days."""
    org_id, key_id = org_and_key
    session_factory = get_session_factory()
    today = datetime.now(UTC).date()

    async with session_factory() as session:
        for i in range(1, 4):
            summary = DailyUsageSummary(
                org_id=org_id,
                api_key_id=key_id,
                netuid=1,
                subnet_name="sn1",
                summary_date=today - timedelta(days=i),
                request_count=10 * i,
                success_count=9 * i,
                error_count=i,
                p50_latency_ms=100 + i * 10,
                p95_latency_ms=200 + i * 10,
                p99_latency_ms=300 + i * 10,
                total_prompt_tokens=100 * i,
                total_completion_tokens=200 * i,
            )
            session.add(summary)
        await session.commit()

    return org_id, key_id


@pytest.mark.asyncio
async def test_get_usage_summaries_returns_data(
    seed_summaries: tuple[uuid.UUID, uuid.UUID],
) -> None:
    org_id, key_id = seed_summaries
    today = datetime.now(UTC).date()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await get_usage_summaries(
            db=session,
            org_id=org_id,
            start_date=today - timedelta(days=7),
            end_date=today,
        )

    assert len(result) >= 1
    sn1 = next((s for s in result if s.netuid == 1), None)
    assert sn1 is not None
    assert len(sn1.summaries) >= 3


@pytest.mark.asyncio
async def test_get_usage_summaries_empty(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    today = datetime.now(UTC).date()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await get_usage_summaries(
            db=session,
            org_id=org_id,
            start_date=today - timedelta(days=7),
            end_date=today,
        )

    assert result == []


@pytest.mark.asyncio
async def test_get_usage_summaries_subnet_filter(
    seed_summaries: tuple[uuid.UUID, uuid.UUID],
) -> None:
    org_id, key_id = seed_summaries
    today = datetime.now(UTC).date()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await get_usage_summaries(
            db=session,
            org_id=org_id,
            start_date=today - timedelta(days=7),
            end_date=today,
            subnet_filter="sn19",  # No SN19 data seeded
        )

    assert result == []


@pytest.mark.asyncio
async def test_get_usage_summaries_monthly_granularity(
    seed_summaries: tuple[uuid.UUID, uuid.UUID],
) -> None:
    org_id, key_id = seed_summaries
    today = datetime.now(UTC).date()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await get_usage_summaries(
            db=session,
            org_id=org_id,
            start_date=today - timedelta(days=7),
            end_date=today,
            granularity="monthly",
        )

    assert len(result) >= 1
    sn1 = next((s for s in result if s.netuid == 1), None)
    assert sn1 is not None
    # Monthly aggregation should collapse daily entries
    for summary in sn1.summaries:
        assert len(summary.period) == 7  # YYYY-MM format


@pytest.mark.asyncio
async def test_get_quota_status(seed_summaries: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = seed_summaries
    session_factory = get_session_factory()

    async with session_factory() as session:
        quotas = await get_quota_status(db=session, org_id=org_id)

    assert len(quotas) == 3  # SN1, SN19, SN62

    sn1_quota = next((q for q in quotas if q.netuid == 1), None)
    assert sn1_quota is not None
    assert sn1_quota.monthly_limit == 1000
    assert sn1_quota.monthly_used > 0
    assert sn1_quota.monthly_remaining == sn1_quota.monthly_limit - sn1_quota.monthly_used


@pytest.mark.asyncio
async def test_get_quota_status_empty(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()

    async with session_factory() as session:
        quotas = await get_quota_status(db=session, org_id=org_id)

    assert len(quotas) == 3
    for q in quotas:
        assert q.monthly_used == 0
        assert q.monthly_remaining == q.monthly_limit
