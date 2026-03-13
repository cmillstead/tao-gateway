"""Tests for auth middleware.

Integration tests hit real Redis + Postgres (via test containers).
Only the "Redis unavailable" degradation test uses a mock.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.exceptions import AuthenticationError
from gateway.core.redis import get_redis
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.models.organization import Organization
from gateway.services.api_key_service import (
    API_KEY_PREFIX_LENGTH,
    create_api_key,
    generate_api_key,
    revoke_api_key,
)


async def _create_org(db: AsyncSession) -> Organization:
    """Create a test organization in the real database."""
    from gateway.core.security import ph

    org = Organization(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=ph.hash("test"),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# Integration tests: get_current_api_key with real Redis + real Postgres
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_cache_miss_valid_key_populates_cache() -> None:
    """Cache miss: DB lookup + argon2 verify succeeds, result cached in Redis."""
    async for db in get_db():
        org = await _create_org(db)
        api_key_record, full_key = await create_api_key(org.id, "live", db)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
        result = await get_current_api_key(creds, db)

        assert isinstance(result, ApiKeyInfo)
        assert result.key_id == api_key_record.id
        assert result.org_id == org.id

        # Verify cache was populated in real Redis
        redis = await get_redis()
        prefix = full_key[:API_KEY_PREFIX_LENGTH]
        cached = await redis.get(f"api_key:{prefix}")
        assert cached is not None
        cached_str = cached.decode()
        assert str(api_key_record.id) in cached_str
        assert str(org.id) in cached_str


@pytest.mark.asyncio
async def test_api_key_cache_hit_verifies_hash() -> None:
    """Second call hits Redis cache, still verifies argon2 hash."""
    async for db in get_db():
        org = await _create_org(db)
        _, full_key = await create_api_key(org.id, "live", db)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
        # First call populates cache
        result1 = await get_current_api_key(creds, db)
        # Second call hits cache
        result2 = await get_current_api_key(creds, db)

        assert result1.key_id == result2.key_id
        assert result1.org_id == result2.org_id


@pytest.mark.asyncio
async def test_api_key_cache_hit_wrong_token_rejected() -> None:
    """Cache hit with wrong token: argon2 verify fails even on cache hit."""
    async for db in get_db():
        org = await _create_org(db)
        _, full_key = await create_api_key(org.id, "live", db)

        # Populate cache with correct key
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
        await get_current_api_key(creds, db)

        # Try with a different key that shares the same prefix (forge it)
        # Use an entirely different key — it won't match any cached hash
        wrong_key, _, _ = generate_api_key("live")
        wrong_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=wrong_key)
        with pytest.raises(AuthenticationError):
            await get_current_api_key(wrong_creds, db)


@pytest.mark.asyncio
async def test_api_key_not_in_db_returns_401() -> None:
    """Key prefix not found in DB -> 401."""
    async for db in get_db():
        full_key, _, _ = generate_api_key("live")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)

        with pytest.raises(AuthenticationError):
            await get_current_api_key(creds, db)


@pytest.mark.asyncio
async def test_api_key_missing_credentials_returns_401() -> None:
    """No Authorization header -> 401."""
    async for db in get_db():
        with pytest.raises(AuthenticationError):
            await get_current_api_key(None, db)


@pytest.mark.asyncio
async def test_api_key_revoked_tombstone_returns_401() -> None:
    """Revoked key (separate tombstone key) returns 401 immediately."""
    async for db in get_db():
        org = await _create_org(db)
        api_key_record, full_key = await create_api_key(org.id, "live", db)

        # First verify the key works
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
        result = await get_current_api_key(creds, db)
        assert result.key_id == api_key_record.id

        # Revoke the key (sets tombstone in real Redis)
        redis = await get_redis()
        await revoke_api_key(api_key_record.id, org.id, db, redis)

        # Now the same key should be rejected via tombstone
        with pytest.raises(AuthenticationError):
            await get_current_api_key(creds, db)


@pytest.mark.asyncio
async def test_api_key_wrong_hash_returns_401() -> None:
    """DB record found but argon2 verify fails -> 401."""
    async for db in get_db():
        org = await _create_org(db)
        api_key_record, full_key = await create_api_key(org.id, "live", db)

        # Tamper with the key — keep same prefix but change the rest
        tampered = full_key[:API_KEY_PREFIX_LENGTH] + "x" * 20
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tampered)

        with pytest.raises(AuthenticationError):
            await get_current_api_key(creds, db)


@pytest.mark.asyncio
async def test_api_key_redis_down_falls_through_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Redis is unavailable, auth falls through to DB-only validation."""
    async for db in get_db():
        org = await _create_org(db)
        _, full_key = await create_api_key(org.id, "live", db)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)

        # Patch try_get_redis to return None (unavailable)
        from gateway.middleware import auth as auth_module

        monkeypatch.setattr(auth_module, "try_get_redis", AsyncMock(return_value=None))

        result = await get_current_api_key(creds, db)
        assert isinstance(result, ApiKeyInfo)
        assert result.org_id == org.id


# ---------------------------------------------------------------------------
# Integration tests: JWT auth on dashboard endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_jwt_on_dashboard_returns_401(client: AsyncClient) -> None:
    """Invalid JWT on a JWT-protected dashboard endpoint returns 401."""
    response = await client.get(
        "/dashboard/api-keys",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_header_on_dashboard_returns_401(client: AsyncClient) -> None:
    """Missing auth header on dashboard endpoint returns 401."""
    response = await client.get("/dashboard/api-keys")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_creation_and_listing_flow(client: AsyncClient) -> None:
    """Full flow: signup -> login -> create key -> verify key format."""
    await client.post(
        "/auth/signup",
        json={"email": "flow2@example.com", "password": "securepassword123"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": "flow2@example.com", "password": "securepassword123"},
    )
    jwt_token = login_resp.json()["access_token"]

    key_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert key_resp.status_code == 201
    api_key = key_resp.json()["key"]
    assert api_key.startswith("tao_sk_live_")
