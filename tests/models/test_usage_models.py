"""Tests for usage record and daily usage summary models."""

import uuid
from datetime import date

import pytest

from gateway.core.database import get_session_factory
from gateway.models.api_key import ApiKey
from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord


@pytest.fixture
async def org_and_key() -> tuple[uuid.UUID, uuid.UUID]:
    """Create a test org and API key, return (org_id, key_id)."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="usage-test@example.com", password_hash="fakehash")
        session.add(org)
        await session.flush()
        key = ApiKey(
            org_id=org.id,
            prefix="tao_sk_test_usage",
            key_hash="fakekeyhash",
        )
        session.add(key)
        await session.commit()
        return org.id, key.id


@pytest.mark.asyncio
async def test_create_usage_record(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()
    async with session_factory() as session:
        record = UsageRecord(
            api_key_id=key_id,
            org_id=org_id,
            subnet_name="sn1",
            netuid=1,
            endpoint="/v1/chat/completions",
            miner_uid="abc12345",
            latency_ms=150,
            status_code=200,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        session.add(record)
        await session.commit()

        result = await session.get(UsageRecord, record.id)
        assert result is not None
        assert result.subnet_name == "sn1"
        assert result.latency_ms == 150
        assert result.status_code == 200
        assert result.prompt_tokens == 10
        assert result.total_tokens == 30
        assert result.created_at is not None


@pytest.mark.asyncio
async def test_usage_record_nullable_miner_uid(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()
    async with session_factory() as session:
        record = UsageRecord(
            api_key_id=key_id,
            org_id=org_id,
            subnet_name="sn1",
            netuid=1,
            endpoint="/v1/chat/completions",
            miner_uid=None,
            latency_ms=0,
            status_code=504,
        )
        session.add(record)
        await session.commit()

        result = await session.get(UsageRecord, record.id)
        assert result is not None
        assert result.miner_uid is None
        assert result.status_code == 504


@pytest.mark.asyncio
async def test_create_daily_usage_summary(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()
    async with session_factory() as session:
        summary = DailyUsageSummary(
            org_id=org_id,
            api_key_id=key_id,
            netuid=1,
            subnet_name="sn1",
            summary_date=date(2026, 3, 13),
            request_count=100,
            success_count=95,
            error_count=5,
            p50_latency_ms=120,
            p95_latency_ms=350,
            p99_latency_ms=500,
            total_prompt_tokens=5000,
            total_completion_tokens=10000,
        )
        session.add(summary)
        await session.commit()

        result = await session.get(DailyUsageSummary, summary.id)
        assert result is not None
        assert result.request_count == 100
        assert result.p95_latency_ms == 350
        assert result.total_prompt_tokens == 5000


@pytest.mark.asyncio
async def test_daily_summary_unique_constraint(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    """Test that duplicate (api_key_id, netuid, summary_date) is rejected."""
    org_id, key_id = org_and_key
    session_factory = get_session_factory()

    async with session_factory() as session:
        summary1 = DailyUsageSummary(
            org_id=org_id,
            api_key_id=key_id,
            netuid=1,
            subnet_name="sn1",
            summary_date=date(2026, 3, 13),
            request_count=50,
        )
        session.add(summary1)
        await session.commit()

    async with session_factory() as session:
        summary2 = DailyUsageSummary(
            org_id=org_id,
            api_key_id=key_id,
            netuid=1,
            subnet_name="sn1",
            summary_date=date(2026, 3, 13),
            request_count=60,
        )
        session.add(summary2)
        with pytest.raises(  # noqa: B017
            Exception,
        ):
            await session.commit()
