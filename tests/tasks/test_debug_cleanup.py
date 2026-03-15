import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from gateway.core.database import get_session_factory
from gateway.models.api_key import ApiKey
from gateway.models.debug_log import DebugLog
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord
from gateway.tasks.debug_cleanup import DebugLogCleanupTask


@pytest.fixture
async def org_and_key() -> tuple[uuid.UUID, uuid.UUID]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        org = Organization(email="debug-cleanup@test.com", password_hash="hash")
        session.add(org)
        await session.flush()
        key = ApiKey(
            org_id=org.id,
            prefix="tao_sk_live_dbgcl",
            key_hash="hash",
            name="cleanup-key",
        )
        session.add(key)
        await session.commit()
        return org.id, key.id


async def _create_debug_entry(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    created_at: datetime,
) -> uuid.UUID:
    session_factory = get_session_factory()
    async with session_factory() as session:
        usage = UsageRecord(
            api_key_id=key_id,
            org_id=org_id,
            subnet_name="sn1",
            netuid=1,
            endpoint="/v1/chat/completions",
            miner_uid="test",
            latency_ms=100,
            status_code=200,
        )
        session.add(usage)
        await session.flush()

        debug_log = DebugLog(
            usage_record_id=usage.id,
            api_key_id=key_id,
            request_body='{"test": "request"}',
            response_body='{"test": "response"}',
        )
        session.add(debug_log)
        await session.flush()

        # Override created_at
        await session.execute(
            update(DebugLog)
            .where(DebugLog.id == debug_log.id)
            .values(created_at=created_at)
        )
        await session.commit()
        return debug_log.id


@pytest.mark.asyncio
async def test_cleanup_deletes_old_entries(org_and_key: tuple[uuid.UUID, uuid.UUID]) -> None:
    org_id, key_id = org_and_key
    session_factory = get_session_factory()
    now = datetime.now(UTC)

    old_id = await _create_debug_entry(org_id, key_id, now - timedelta(hours=49))
    recent_id = await _create_debug_entry(org_id, key_id, now - timedelta(hours=1))

    task = DebugLogCleanupTask(session_factory=session_factory, retention_hours=48)
    deleted = await task.cleanup_once()
    assert deleted == 1

    async with session_factory() as session:
        old = await session.scalar(select(DebugLog).where(DebugLog.id == old_id))
        assert old is None

        recent = await session.scalar(select(DebugLog).where(DebugLog.id == recent_id))
        assert recent is not None


@pytest.mark.asyncio
async def test_cleanup_no_entries() -> None:
    session_factory = get_session_factory()
    task = DebugLogCleanupTask(session_factory=session_factory, retention_hours=48)
    deleted = await task.cleanup_once()
    assert deleted == 0
