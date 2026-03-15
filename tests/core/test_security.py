"""Tests for gateway.core.security — try_rehash."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.security import ph, try_rehash
from gateway.models.organization import Organization


async def _create_org(db: AsyncSession) -> Organization:
    import uuid

    org = Organization(
        email=f"rehash-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=ph.hash("test-password"),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest.mark.asyncio
async def test_try_rehash_noop_when_current():
    """No DB write when hash params are already current."""
    async for db in get_db():
        org = await _create_org(db)
        original_hash = org.password_hash
        await try_rehash(db, org, "password_hash", "test-password")
        assert org.password_hash == original_hash


@pytest.mark.asyncio
async def test_try_rehash_silently_catches_errors():
    """Rehash failure is silently caught, does not propagate."""
    async for db in get_db():
        org = await _create_org(db)
        # Corrupt the hash so check_needs_rehash raises
        org.password_hash = "not-a-valid-argon2-hash"
        # Should not raise — failure is silently caught
        await try_rehash(db, org, "password_hash", "test-password")
