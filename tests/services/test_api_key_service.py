"""Tests for API key service.

Unit tests for key generation + integration tests hitting real Postgres and Redis.
"""

import uuid

import pytest
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.exceptions import GatewayError
from gateway.core.redis import get_redis
from gateway.core.security import ph as app_ph
from gateway.models.api_key import ApiKey
from gateway.models.organization import Organization
from gateway.services.api_key_service import (
    API_KEY_PREFIX_LENGTH,
    MAX_KEYS_PER_ORG,
    create_api_key,
    generate_api_key,
    list_api_keys,
    revoke_api_key,
)

ph = PasswordHasher()


async def _create_org(db: AsyncSession) -> Organization:
    """Create a test organization in the real database."""
    org = Organization(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=app_ph.hash("test"),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# Unit tests: generate_api_key (no DB needed)
# ---------------------------------------------------------------------------


def test_generate_api_key_live_format() -> None:
    full_key, prefix, key_hash = generate_api_key("live")
    assert full_key.startswith("tao_sk_live_")
    assert len(prefix) == 20
    assert full_key[:20] == prefix
    assert key_hash != full_key


def test_generate_api_key_test_format() -> None:
    full_key, prefix, key_hash = generate_api_key("test")
    assert full_key.startswith("tao_sk_test_")
    assert len(prefix) == 20


def test_generate_api_key_hash_is_argon2() -> None:
    full_key, _prefix, key_hash = generate_api_key("live")
    assert key_hash.startswith("$argon2")
    assert ph.verify(key_hash, full_key)


def test_generate_api_key_uniqueness() -> None:
    key1 = generate_api_key("live")
    key2 = generate_api_key("live")
    assert key1[0] != key2[0]
    assert key1[1] != key2[1]
    assert key1[2] != key2[2]


def test_generate_api_key_hash_not_plaintext() -> None:
    full_key, _prefix, key_hash = generate_api_key("live")
    assert full_key not in key_hash


# ---------------------------------------------------------------------------
# Integration tests: create/list/revoke with real Postgres + Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_api_key_persists_to_db() -> None:
    """create_api_key persists a new key record and returns it with the full key."""
    async for db in get_db():
        org = await _create_org(db)
        api_key, full_key = await create_api_key(org.id, "live", db)

        assert api_key.org_id == org.id
        assert api_key.is_active is True
        assert full_key.startswith("tao_sk_live_")
        assert api_key.prefix == full_key[:API_KEY_PREFIX_LENGTH]

        # Verify it's in the DB
        db_key = await db.get(ApiKey, api_key.id)
        assert db_key is not None
        assert db_key.is_active is True


@pytest.mark.asyncio
async def test_create_api_key_max_keys_boundary() -> None:
    """create_api_key rejects when org already has MAX_KEYS_PER_ORG active keys."""
    async for db in get_db():
        org = await _create_org(db)

        # Create MAX_KEYS_PER_ORG keys
        for _ in range(MAX_KEYS_PER_ORG):
            await create_api_key(org.id, "live", db)

        # The next one should fail
        with pytest.raises(GatewayError, match="Maximum of"):
            await create_api_key(org.id, "live", db)


@pytest.mark.asyncio
async def test_revoke_api_key_sets_tombstone() -> None:
    """revoke_api_key sets is_active=False and writes a Redis tombstone."""
    async for db in get_db():
        org = await _create_org(db)
        api_key, full_key = await create_api_key(org.id, "live", db)
        redis = await get_redis()

        revoked = await revoke_api_key(api_key.id, org.id, db, redis)

        assert revoked is not None
        assert revoked.is_active is False

        # Tombstone exists in real Redis
        tombstone_key = f"api_key_revoked:{api_key.prefix}"
        assert await redis.exists(tombstone_key)

        # Cache entry deleted
        cache_key = f"api_key:{api_key.prefix}"
        assert not await redis.exists(cache_key)


@pytest.mark.asyncio
async def test_cross_tenant_isolation() -> None:
    """An org cannot revoke another org's API key."""
    async for db in get_db():
        org_a = await _create_org(db)
        org_b = await _create_org(db)
        api_key_a, _ = await create_api_key(org_a.id, "live", db)
        redis = await get_redis()

        # org_b tries to revoke org_a's key
        result = await revoke_api_key(api_key_a.id, org_b.id, db, redis)
        assert result is None  # Not found for org_b

        # Verify key is still active
        db_key = await db.get(ApiKey, api_key_a.id)
        assert db_key is not None
        assert db_key.is_active is True


@pytest.mark.asyncio
async def test_list_api_keys_count() -> None:
    """list_api_keys returns correct keys and total count."""
    async for db in get_db():
        org = await _create_org(db)

        # Create 3 keys
        for _ in range(3):
            await create_api_key(org.id, "live", db)

        keys, total = await list_api_keys(org.id, db)
        assert total == 3
        assert len(keys) == 3
        assert all(k.org_id == org.id for k in keys)

        # Pagination: limit=2
        keys_page, total_page = await list_api_keys(org.id, db, limit=2)
        assert len(keys_page) == 2
        assert total_page == 3
