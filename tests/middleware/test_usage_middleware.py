"""Tests for fire-and-forget usage recording middleware."""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from gateway.core.database import get_session_factory
from gateway.middleware.usage import record_usage
from gateway.models.api_key import ApiKey
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord


@pytest.fixture
async def org_and_key() -> tuple[uuid.UUID, uuid.UUID]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="middleware-test@example.com", password_hash="fakehash")
        session.add(org)
        await session.flush()
        key = ApiKey(org_id=org.id, prefix="tao_sk_test_mw", key_hash="fakekeyhash")
        session.add(key)
        await session.commit()
        return org.id, key.id


@pytest.mark.asyncio
async def test_record_usage_writes_to_db(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()

    await record_usage(
        session_factory=session_factory,
        api_key_id=key_id,
        org_id=org_id,
        subnet_name="sn1",
        netuid=1,
        endpoint="/v1/chat/completions",
        miner_uid="abc12345",
        latency_ms=200,
        status_code=200,
        prompt_tokens=5,
        completion_tokens=10,
        total_tokens=15,
    )

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(UsageRecord))
        assert count == 1

        record = await session.scalar(select(UsageRecord))
        assert record is not None
        assert record.subnet_name == "sn1"
        assert record.latency_ms == 200
        assert record.prompt_tokens == 5


@pytest.mark.asyncio
async def test_record_usage_fire_and_forget(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    """Verify fire-and-forget via create_task doesn't block."""
    org_id, key_id = org_and_key
    session_factory = get_session_factory()

    task = asyncio.create_task(record_usage(
        session_factory=session_factory,
        api_key_id=key_id,
        org_id=org_id,
        subnet_name="sn1",
        netuid=1,
        endpoint="/v1/chat/completions",
        miner_uid="abc12345",
        latency_ms=100,
        status_code=200,
    ))

    # Let the task complete
    await asyncio.sleep(0.1)
    assert task.done()

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(UsageRecord))
        assert count == 1


@pytest.mark.asyncio
async def test_record_usage_exception_handling() -> None:
    """Verify that record_usage catches exceptions and doesn't crash."""
    session_factory = get_session_factory()

    # Use invalid UUIDs to trigger a DB error (FK constraint)
    await record_usage(
        session_factory=session_factory,
        api_key_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        subnet_name="sn1",
        netuid=1,
        endpoint="/v1/chat/completions",
        miner_uid=None,
        latency_ms=0,
        status_code=500,
    )
    # Should not raise — just log warning
