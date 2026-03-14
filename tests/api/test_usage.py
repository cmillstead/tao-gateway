"""Tests for usage API endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from gateway.core.database import get_session_factory
from gateway.middleware.usage import record_usage
from gateway.models.api_key import ApiKey
from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord
from gateway.services.api_key_service import generate_api_key
from gateway.services.auth_service import create_jwt_token


@pytest.fixture
async def auth_setup() -> dict:
    """Create org, API key, and return auth info."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="api-usage-test@example.com", password_hash="fakehash")
        session.add(org)
        await session.flush()

        full_key, prefix, key_hash = generate_api_key()
        key = ApiKey(org_id=org.id, prefix=prefix, key_hash=key_hash)
        session.add(key)
        await session.commit()

        jwt = create_jwt_token(str(org.id))

        return {
            "org_id": org.id,
            "key_id": key.id,
            "raw_key": full_key,
            "bearer_headers": {"Authorization": f"Bearer {full_key}"},
            "jwt_headers": {"Authorization": f"Bearer {jwt}"},
        }


@pytest.fixture
async def seeded_auth(auth_setup: dict) -> dict:
    """auth_setup with seeded daily summaries."""
    session_factory = get_session_factory()
    today = datetime.now(UTC).date()
    async with session_factory() as session:
        for i in range(1, 4):
            session.add(DailyUsageSummary(
                org_id=auth_setup["org_id"],
                api_key_id=auth_setup["key_id"],
                netuid=1,
                subnet_name="sn1",
                summary_date=today - timedelta(days=i),
                request_count=10 * i,
                success_count=9 * i,
                error_count=i,
                p50_latency_ms=100,
                p95_latency_ms=200,
                p99_latency_ms=300,
                total_prompt_tokens=50 * i,
                total_completion_tokens=100 * i,
            ))
        await session.commit()
    return auth_setup


@pytest.mark.asyncio
async def test_get_v1_usage(client: AsyncClient, seeded_auth: dict) -> None:
    resp = await client.get("/v1/usage", headers=seeded_auth["bearer_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "subnets" in data
    assert "start_date" in data
    assert "end_date" in data
    assert data["granularity"] == "daily"


@pytest.mark.asyncio
async def test_get_v1_usage_empty(client: AsyncClient, auth_setup: dict) -> None:
    resp = await client.get("/v1/usage", headers=auth_setup["bearer_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["subnets"] == []


@pytest.mark.asyncio
async def test_get_v1_usage_with_subnet_filter(client: AsyncClient, seeded_auth: dict) -> None:
    resp = await client.get(
        "/v1/usage",
        params={"subnet": "sn1"},
        headers=seeded_auth["bearer_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for subnet in data["subnets"]:
        assert subnet["subnet_name"] == "sn1"


@pytest.mark.asyncio
async def test_get_v1_usage_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/v1/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_usage(client: AsyncClient, seeded_auth: dict) -> None:
    resp = await client.get("/dashboard/usage", headers=seeded_auth["jwt_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "subnets" in data


@pytest.mark.asyncio
async def test_get_dashboard_usage_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/dashboard/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_v1_usage_invalid_granularity(
    client: AsyncClient, auth_setup: dict,
) -> None:
    """Invalid granularity returns 422."""
    resp = await client.get(
        "/v1/usage",
        params={"granularity": "foobar"},
        headers=auth_setup["bearer_headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_usage_recording_integration(auth_setup: dict) -> None:
    """Verify record_usage writes to DB (integration test for Task 9.6)."""
    session_factory = get_session_factory()

    await record_usage(
        session_factory=session_factory,
        api_key_id=auth_setup["key_id"],
        org_id=auth_setup["org_id"],
        subnet_name="sn1",
        netuid=1,
        endpoint="/v1/chat/completions",
        miner_uid="test_miner",
        latency_ms=150,
        status_code=200,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(UsageRecord)
        )
        assert count == 1

        record = await session.scalar(select(UsageRecord))
        assert record is not None
        assert record.api_key_id == auth_setup["key_id"]
        assert record.org_id == auth_setup["org_id"]
        assert record.subnet_name == "sn1"
        assert record.latency_ms == 150
