"""Tests for cookie-based dashboard authentication.

Covers: POST /auth/login/dashboard, POST /auth/refresh, POST /auth/logout.
Uses real Postgres and Redis — no mocks.
"""

import uuid

import pytest
from httpx import AsyncClient

from gateway.services import auth_service


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict[str, str]:
    """Create a test user and return credentials."""
    email = f"cookie-test-{uuid.uuid4().hex[:8]}@example.com"
    password = "test-password-123"
    resp = await client.post("/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201, f"Fixture signup failed: {resp.text}"
    return {"email": email, "password": password}


async def test_dashboard_login_sets_cookies(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    resp = await client.post("/auth/login/dashboard", json=registered_user)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Login successful"

    cookies = resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies


async def test_dashboard_login_invalid_credentials(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login/dashboard",
        json={"email": "nobody@example.com", "password": "wrong-password-123"},
    )
    assert resp.status_code == 401


async def test_refresh_issues_new_tokens(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    # Login first to get cookies
    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    assert login_resp.status_code == 200
    old_refresh = login_resp.cookies["refresh_token"]

    # Refresh — must send the refresh_token cookie
    refresh_resp = await client.post(
        "/auth/refresh",
        cookies={"refresh_token": old_refresh},
    )
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["message"] == "Token refreshed"

    new_refresh = refresh_resp.cookies["refresh_token"]
    # Access token may be identical if generated in the same second (same iat/exp),
    # but the refresh token must always differ (new random value).
    assert new_refresh != old_refresh
    assert "access_token" in refresh_resp.cookies


async def test_refresh_invalid_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/refresh",
        cookies={"refresh_token": "invalid-token"},
    )
    assert resp.status_code == 401


async def test_refresh_missing_cookie(client: AsyncClient) -> None:
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_token_rotation_revokes_old(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    """After rotation, the old refresh token should be rejected."""
    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    old_refresh = login_resp.cookies["refresh_token"]

    # Rotate
    await client.post("/auth/refresh", cookies={"refresh_token": old_refresh})

    # Try to use old refresh token again
    resp = await client.post(
        "/auth/refresh",
        cookies={"refresh_token": old_refresh},
    )
    assert resp.status_code == 401


async def test_logout_clears_cookies(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    refresh_token = login_resp.cookies["refresh_token"]

    logout_resp = await client.post(
        "/auth/logout",
        cookies={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out"

    # The refresh token should be revoked
    resp = await client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401


async def test_logout_without_cookie(client: AsyncClient) -> None:
    """Logout without a cookie should still succeed (idempotent)."""
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200


async def test_cookie_auth_on_dashboard_endpoints(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    """Dashboard API endpoints should accept cookie auth."""
    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    access_token = login_resp.cookies["access_token"]

    # Access dashboard API with cookie only (no Bearer header)
    resp = await client.get(
        "/dashboard/api-keys",
        cookies={"access_token": access_token},
    )
    assert resp.status_code == 200


async def test_bearer_auth_still_works(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    """Existing Bearer token flow must continue to work."""
    login_resp = await client.post("/auth/login", json=registered_user)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/dashboard/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_refresh_expired_token(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    """An expired refresh token should be rejected."""
    from datetime import UTC, datetime, timedelta

    from gateway.core.database import get_session_factory
    from gateway.models.refresh_token import RefreshToken

    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    refresh_token_value = login_resp.cookies["refresh_token"]

    # Manually expire the token in DB
    token_hash = auth_service._hash_refresh_token(refresh_token_value)
    async with get_session_factory()() as db:
        from sqlalchemy import select

        record = await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

    resp = await client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_token_value},
    )
    assert resp.status_code == 401


async def test_auth_me_returns_user_info(
    client: AsyncClient, registered_user: dict[str, str]
) -> None:
    """GET /auth/me returns user id and email when authenticated via cookie."""
    login_resp = await client.post("/auth/login/dashboard", json=registered_user)
    access_token = login_resp.cookies["access_token"]

    resp = await client.get("/auth/me", cookies={"access_token": access_token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == registered_user["email"]
    assert data["id"]  # non-empty UUID string
    assert data["is_admin"] is False  # regular users are not admin


async def test_auth_me_returns_is_admin_true_for_admin(
    client: AsyncClient,
) -> None:
    """GET /auth/me returns is_admin=True for admin users."""
    from sqlalchemy import update

    from gateway.core.database import get_session_factory
    from gateway.models.organization import Organization

    # Create user and login
    email = f"admin-me-{uuid.uuid4().hex[:8]}@example.com"
    password = "test-password-123"
    resp = await client.post("/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201

    # Promote to admin directly in DB
    async with get_session_factory()() as db:
        await db.execute(
            update(Organization).where(Organization.email == email).values(is_admin=True)
        )
        await db.commit()

    creds = {"email": email, "password": password}
    login_resp = await client.post("/auth/login/dashboard", json=creds)
    access_token = login_resp.cookies["access_token"]

    resp = await client.get(
        "/auth/me", cookies={"access_token": access_token}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_admin"] is True


async def test_auth_me_unauthenticated(client: AsyncClient) -> None:
    """GET /auth/me returns 401 without auth."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_refresh_token_service_functions() -> None:
    """Test the SHA-256 hashing is deterministic."""
    token = "test-token-value"
    hash1 = auth_service._hash_refresh_token(token)
    hash2 = auth_service._hash_refresh_token(token)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest
