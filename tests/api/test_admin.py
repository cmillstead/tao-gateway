"""Tests for admin API endpoints (Story 6.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_session_factory
from gateway.main import app
from gateway.models.api_key import ApiKey
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord
from gateway.routing.scorer import MinerScorer, ScoreObservation
from gateway.services.auth_service import create_jwt_token


async def _create_org(
    db: AsyncSession,
    email: str = "admin@test.com",
    is_admin: bool = False,
) -> Organization:
    """Create a test org and return it."""
    from gateway.core.security import ph

    org = Organization(
        email=email,
        password_hash=ph.hash("testpassword"),
        is_admin=is_admin,
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


async def _create_admin_client(
    email: str = "admin@test.com",
) -> tuple[AsyncClient, Organization]:
    """Create admin org with JWT and return (client, org)."""
    async with get_session_factory()() as db:
        org = await _create_org(db, email=email, is_admin=True)
        await db.commit()
        await db.refresh(org)
    token = create_jwt_token(str(org.id))
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": token},
    )
    return client, org


async def _create_regular_client(
    email: str = "dev@test.com",
) -> tuple[AsyncClient, Organization]:
    """Create non-admin org with JWT and return (client, org)."""
    async with get_session_factory()() as db:
        org = await _create_org(db, email=email, is_admin=False)
        await db.commit()
        await db.refresh(org)
    token = create_jwt_token(str(org.id))
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": token},
    )
    return client, org


async def _create_api_key(db: AsyncSession, org_id: uuid.UUID) -> ApiKey:
    """Create a test API key for usage records."""
    key = ApiKey(
        org_id=org_id,
        prefix="tao_test_prefix_" + uuid.uuid4().hex[:8],
        key_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
    )
    db.add(key)
    await db.flush()
    await db.refresh(key)
    return key


async def _add_usage_records(
    org_id: uuid.UUID,
    count: int = 5,
    subnet_name: str = "sn1",
    netuid: int = 1,
    status_code: int = 200,
) -> None:
    """Insert usage records for an org."""
    async with get_session_factory()() as db:
        key = await _create_api_key(db, org_id)
        for i in range(count):
            record = UsageRecord(
                api_key_id=key.id,
                org_id=org_id,
                subnet_name=subnet_name,
                netuid=netuid,
                endpoint="/v1/chat/completions",
                latency_ms=100 + i * 10,
                status_code=status_code,
                prompt_tokens=50,
                completion_tokens=100,
                total_tokens=150,
            )
            db.add(record)
        await db.commit()


# --- Model Tests ---


@pytest.mark.asyncio
async def test_organization_is_admin_default():
    """is_admin column exists and defaults to False."""
    async with get_session_factory()() as db:
        org = await _create_org(db, email="default@test.com")
        await db.commit()
        assert org.is_admin is False


@pytest.mark.asyncio
async def test_organization_is_admin_true():
    """is_admin can be set to True."""
    async with get_session_factory()() as db:
        org = await _create_org(db, email="admin@test.com", is_admin=True)
        await db.commit()
        assert org.is_admin is True


# --- Auth Tests ---


@pytest.mark.asyncio
async def test_admin_endpoint_returns_401_without_auth():
    """Admin endpoints return 401 when not authenticated."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/admin/metrics")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_returns_403_for_non_admin():
    """Admin endpoints return 403 for authenticated non-admin users."""
    client, _org = await _create_regular_client()
    async with client:
        resp = await client.get("/admin/metrics")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["type"] == "authorization_error"


@pytest.mark.asyncio
async def test_admin_endpoint_allows_admin():
    """Admin endpoints return 200 for admin users."""
    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/metrics")
        assert resp.status_code == 200


# --- GET /admin/metrics ---


@pytest.mark.asyncio
async def test_metrics_empty():
    """Metrics returns empty subnets when no usage data."""
    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/metrics?time_range=24h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["time_range"] == "24h"
        assert data["total_requests"] == 0
        assert data["total_errors"] == 0
        assert data["overall_error_rate"] == 0.0
        assert data["subnets"] == []


@pytest.mark.asyncio
async def test_metrics_with_data():
    """Metrics returns per-subnet aggregation from live usage records."""
    client, org = await _create_admin_client()
    await _add_usage_records(org.id, count=3, subnet_name="sn1", netuid=1)
    await _add_usage_records(org.id, count=2, subnet_name="sn1", netuid=1, status_code=500)

    async with client:
        resp = await client.get("/admin/metrics?time_range=24h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 5
        assert data["total_errors"] == 2
        assert len(data["subnets"]) == 1
        subnet = data["subnets"][0]
        assert subnet["subnet_name"] == "sn1"
        assert subnet["request_count"] == 5
        assert subnet["success_count"] == 3
        assert subnet["error_count"] == 2


@pytest.mark.asyncio
async def test_metrics_1h_time_range():
    """Metrics with 1h time range uses live records only."""
    client, org = await _create_admin_client()
    await _add_usage_records(org.id, count=3, subnet_name="sn1", netuid=1)

    async with client:
        resp = await client.get("/admin/metrics?time_range=1h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["time_range"] == "1h"
        assert data["total_requests"] == 3


@pytest.mark.asyncio
async def test_metrics_invalid_time_range():
    """Invalid time range is rejected by query validation."""
    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/metrics?time_range=2h")
        assert resp.status_code == 422


# --- GET /admin/metagraph ---


@pytest.mark.asyncio
async def test_metagraph_returns_subnet_status():
    """Metagraph endpoint returns sync status for registered subnets."""
    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/metagraph")
        assert resp.status_code == 200
        data = resp.json()
        assert "subnets" in data
        # Should have subnets from test metagraph manager
        assert len(data["subnets"]) > 0
        subnet = data["subnets"][0]
        assert "netuid" in subnet
        assert "sync_status" in subnet
        assert "staleness_seconds" in subnet
        assert "active_miners" in subnet


# --- GET /admin/developers ---


@pytest.mark.asyncio
async def test_developers_returns_metrics():
    """Developers endpoint returns signup and activity metrics."""
    client, admin_org = await _create_admin_client()
    # Create additional dev
    async with get_session_factory()() as db:
        await _create_org(db, email="dev1@test.com")
        await db.commit()

    async with client:
        resp = await client.get("/admin/developers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_developers"] == 2  # admin + dev
        assert data["new_signups_today"] == 2
        assert data["new_signups_this_week"] == 2
        assert isinstance(data["developers"], list)
        assert len(data["developers"]) == 2


@pytest.mark.asyncio
async def test_developers_with_usage():
    """Developer summary includes per-subnet request counts."""
    client, admin_org = await _create_admin_client()
    await _add_usage_records(admin_org.id, count=3, subnet_name="sn1", netuid=1)

    async with client:
        resp = await client.get("/admin/developers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["weekly_active_developers"] == 1
        # Find admin dev in list
        admin_dev = next(
            (d for d in data["developers"] if d["org_id"] == str(admin_org.id)),
            None,
        )
        assert admin_dev is not None
        assert admin_dev["total_requests"] == 3
        assert admin_dev["requests_by_subnet"]["sn1"] == 3


# --- GET /admin/miners ---


@pytest.mark.asyncio
async def test_miners_returns_quality_data(test_app):
    """Miners endpoint returns quality data from scorer."""
    # Set up a scorer with some test data
    scorer = MinerScorer()
    scorer.record_observation(
        ScoreObservation(
            miner_uid=42,
            hotkey="test_hotkey_42",
            netuid=1,
            success=True,
            latency_ms=200.0,
            response_valid=True,
            response_complete=True,
            timestamp=datetime.now(UTC),
        )
    )
    test_app.state.scorer = scorer

    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/miners")
        assert resp.status_code == 200
        data = resp.json()
        assert "subnets" in data
        if "sn1" in data["subnets"]:
            miners = data["subnets"]["sn1"]
            assert len(miners) == 1
            assert miners[0]["miner_uid"] == 42
            assert miners[0]["hotkey"] == "test_hotkey_42"
            assert miners[0]["total_requests"] == 1
            assert miners[0]["successful_requests"] == 1


@pytest.mark.asyncio
async def test_miners_empty_when_no_scorer(test_app):
    """Miners endpoint returns empty when scorer is None."""
    test_app.state.scorer = None

    client, _org = await _create_admin_client()
    async with client:
        resp = await client.get("/admin/miners")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subnets"] == {}


@pytest.mark.asyncio
async def test_metrics_multi_subnet():
    """Metrics aggregates correctly across multiple subnets."""
    client, org = await _create_admin_client()
    await _add_usage_records(org.id, count=3, subnet_name="sn1", netuid=1)
    await _add_usage_records(org.id, count=2, subnet_name="sn19", netuid=19)

    async with client:
        resp = await client.get("/admin/metrics?time_range=24h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 5
        assert len(data["subnets"]) == 2
        subnet_names = {s["subnet_name"] for s in data["subnets"]}
        assert subnet_names == {"sn1", "sn19"}


@pytest.mark.asyncio
async def test_miners_with_netuid_filter(test_app):
    """Miners endpoint filters by netuid when provided."""
    scorer = MinerScorer()
    scorer.record_observation(
        ScoreObservation(
            miner_uid=1, hotkey="hk1", netuid=1,
            success=True, latency_ms=100.0,
            response_valid=True, response_complete=True,
            timestamp=datetime.now(UTC),
        )
    )
    scorer.record_observation(
        ScoreObservation(
            miner_uid=2, hotkey="hk2", netuid=19,
            success=True, latency_ms=200.0,
            response_valid=True, response_complete=True,
            timestamp=datetime.now(UTC),
        )
    )
    test_app.state.scorer = scorer

    client, _org = await _create_admin_client()
    async with client:
        # Filter to netuid=1 only
        resp = await client.get("/admin/miners?netuid=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "sn1" in data["subnets"]
        assert "sn19" not in data["subnets"]


# --- Auth boundary tests for all endpoints ---


@pytest.mark.asyncio
async def test_all_admin_endpoints_require_auth():
    """All /admin/* endpoints return 401 without auth."""
    endpoints = ["/admin/metrics", "/admin/metagraph", "/admin/developers", "/admin/miners"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for endpoint in endpoints:
            resp = await client.get(endpoint)
            assert resp.status_code == 401, f"{endpoint} should return 401"


@pytest.mark.asyncio
async def test_all_admin_endpoints_require_admin_role():
    """All /admin/* endpoints return 403 for non-admin users."""
    endpoints = ["/admin/metrics", "/admin/metagraph", "/admin/developers", "/admin/miners"]
    client, _org = await _create_regular_client()
    async with client:
        for endpoint in endpoints:
            resp = await client.get(endpoint)
            assert resp.status_code == 403, f"{endpoint} should return 403 for non-admin"


# --- OpenAPI schema exclusion ---


@pytest.mark.asyncio
async def test_admin_endpoints_not_in_openapi():
    """Admin endpoints should not appear in the public OpenAPI schema."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        paths = schema.get("paths", {})
        admin_paths = [p for p in paths if p.startswith("/admin")]
        assert admin_paths == [], f"Admin paths should not be in OpenAPI: {admin_paths}"
