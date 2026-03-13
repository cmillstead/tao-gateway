"""Tests for auth middleware.

Unit tests for get_current_api_key directly test Redis cache hit/miss
behavior with mocked dependencies. Integration tests validate end-to-end
JWT auth on dashboard endpoints (API key protected endpoints arrive in Story 1.4+).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient

from gateway.core.exceptions import AuthenticationError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.services.api_key_service import generate_api_key

# ---------------------------------------------------------------------------
# Unit tests: get_current_api_key with mocked redis + db
# ---------------------------------------------------------------------------


def _patch_redis(monkeypatch: pytest.MonkeyPatch, mock_redis: AsyncMock) -> None:
    """Patch _try_get_redis to return the given mock."""
    from gateway.middleware import auth as auth_module

    monkeypatch.setattr(auth_module, "_try_get_redis", AsyncMock(return_value=mock_redis))


@pytest.mark.asyncio
async def test_api_key_cache_hit_verifies_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache hit: Redis returns cached key_hash:key_id:org_id, hash is verified."""
    key_id = uuid.uuid4()
    org_id = uuid.uuid4()
    full_key, prefix, key_hash = generate_api_key("live")

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.get.return_value = f"{key_hash}:{key_id}:{org_id}".encode()
    mock_db = AsyncMock()

    _patch_redis(monkeypatch, mock_redis)
    result = await get_current_api_key(mock_credentials, mock_db)

    assert isinstance(result, ApiKeyInfo)
    assert result.key_id == key_id
    assert result.org_id == org_id
    mock_redis.get.assert_called_once_with(f"api_key:{prefix}")
    mock_db.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_api_key_cache_hit_wrong_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache hit with wrong token: hash verification fails even on cache hit."""
    key_id = uuid.uuid4()
    org_id = uuid.uuid4()
    _, _, real_hash = generate_api_key("live")
    wrong_key, wrong_prefix, _ = generate_api_key("live")

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=wrong_key)
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.get.return_value = f"{real_hash}:{key_id}:{org_id}".encode()
    mock_db = AsyncMock()

    _patch_redis(monkeypatch, mock_redis)
    with pytest.raises(AuthenticationError):
        await get_current_api_key(mock_credentials, mock_db)


@pytest.mark.asyncio
async def test_api_key_cache_miss_valid_key_caches_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache miss: DB lookup + argon2 verify succeeds, result cached with 60s TTL."""
    full_key, prefix, key_hash = generate_api_key("live")
    key_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_api_key = MagicMock()
    mock_api_key.id = key_id
    mock_api_key.org_id = org_id
    mock_api_key.key_hash = key_hash

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.get.return_value = None
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_api_key

    _patch_redis(monkeypatch, mock_redis)
    result = await get_current_api_key(mock_credentials, mock_db)

    assert isinstance(result, ApiKeyInfo)
    assert result.key_id == key_id
    assert result.org_id == org_id
    # Cache value now includes hash
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    cache_val = call_args[0][1]
    assert cache_val.startswith("$argon2")
    assert str(key_id) in cache_val
    assert str(org_id) in cache_val
    assert call_args[1]["ex"] == 60


@pytest.mark.asyncio
async def test_api_key_cache_miss_wrong_hash_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache miss: DB record found but argon2 verify fails -> 401."""
    full_key, prefix, _ = generate_api_key("live")
    _, _, wrong_hash = generate_api_key("live")  # hash of a different key

    mock_api_key = MagicMock()
    mock_api_key.id = uuid.uuid4()
    mock_api_key.org_id = uuid.uuid4()
    mock_api_key.key_hash = wrong_hash

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.get.return_value = None
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_api_key

    _patch_redis(monkeypatch, mock_redis)
    with pytest.raises(AuthenticationError):
        await get_current_api_key(mock_credentials, mock_db)


@pytest.mark.asyncio
async def test_api_key_not_in_db_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache miss: key prefix not found in DB -> 401."""
    full_key, _, _ = generate_api_key("live")

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.get.return_value = None
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None

    _patch_redis(monkeypatch, mock_redis)
    with pytest.raises(AuthenticationError):
        await get_current_api_key(mock_credentials, mock_db)


@pytest.mark.asyncio
async def test_api_key_missing_credentials_returns_401() -> None:
    """No Authorization header -> 401."""
    mock_db = AsyncMock()

    with pytest.raises(AuthenticationError):
        await get_current_api_key(None, mock_db)


@pytest.mark.asyncio
async def test_api_key_revoked_tombstone_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Revoked key (separate tombstone key) returns 401 immediately."""
    full_key, prefix, _ = generate_api_key("live")

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_redis = AsyncMock()
    # Tombstone is now a separate key: api_key_revoked:{prefix}
    mock_redis.exists.return_value = True
    mock_db = AsyncMock()

    _patch_redis(monkeypatch, mock_redis)
    with pytest.raises(AuthenticationError):
        await get_current_api_key(mock_credentials, mock_db)

    # DB should never be queried for a tombstoned key
    mock_db.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_api_key_redis_down_falls_through_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Redis is unavailable, auth falls through to DB-only validation."""
    full_key, prefix, key_hash = generate_api_key("live")
    key_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_api_key = MagicMock()
    mock_api_key.id = key_id
    mock_api_key.org_id = org_id
    mock_api_key.key_hash = key_hash

    mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=full_key)
    mock_db = AsyncMock()
    mock_db.scalar.return_value = mock_api_key

    # Redis returns None (unavailable)
    from gateway.middleware import auth as auth_module

    monkeypatch.setattr(auth_module, "_try_get_redis", AsyncMock(return_value=None))

    result = await get_current_api_key(mock_credentials, mock_db)

    assert isinstance(result, ApiKeyInfo)
    assert result.key_id == key_id
    assert result.org_id == org_id
    mock_db.scalar.assert_called_once()


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
