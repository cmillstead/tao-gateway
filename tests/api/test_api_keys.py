import pytest
from httpx import AsyncClient


async def _signup_and_get_jwt(client: AsyncClient, email: str) -> str:
    """Helper: signup + login, return JWT token."""
    await client.post(
        "/auth/signup",
        json={"email": email, "password": "securepassword123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_api_key_returns_full_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "keytest@example.com")
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("tao_sk_live_")
    assert "prefix" in data
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_test_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "testkey@example.com")
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["key"].startswith("tao_sk_test_")


@pytest.mark.asyncio
async def test_list_api_keys_masked(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "listkeys@example.com")
    # Create a key first
    create_response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.json()["key"].startswith("tao_sk_live_")  # full key returned at creation

    # List keys — should not contain full key
    response = await client.get(
        "/dashboard/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    for key in data["items"]:
        assert "prefix" in key
        assert "key" not in key  # Full key should NOT be in list response
        assert "is_active" in key


@pytest.mark.asyncio
async def test_create_api_key_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "revoke@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers,
    )
    key_id = create_resp.json()["id"]

    revoke_resp = await client.delete(
        f"/dashboard/api-keys/{key_id}",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["message"] == "API key revoked"

    # Verify revoked key is excluded from default listing
    list_resp = await client.get("/dashboard/api-keys", headers=headers)
    keys = list_resp.json()["items"]
    assert not any(k["id"] == key_id for k in keys)


@pytest.mark.asyncio
async def test_revoke_nonexistent_key_returns_404(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "revoke404@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete(
        "/dashboard/api-keys/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_other_orgs_key_returns_404(client: AsyncClient) -> None:
    """Org A cannot revoke org B's key (cross-tenant isolation)."""
    token_a = await _signup_and_get_jwt(client, "org_a@example.com")
    token_b = await _signup_and_get_jwt(client, "org_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org B creates a key
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers=headers_b,
    )
    key_id_b = create_resp.json()["id"]

    # Org A tries to revoke org B's key
    revoke_resp = await client.delete(
        f"/dashboard/api-keys/{key_id_b}",
        headers=headers_a,
    )
    assert revoke_resp.status_code == 404

    # Verify key is still active for org B
    list_resp = await client.get("/dashboard/api-keys", headers=headers_b)
    keys = list_resp.json()["items"]
    assert any(k["id"] == key_id_b and k["is_active"] for k in keys)


@pytest.mark.asyncio
async def test_list_api_keys_pagination_bounds(client: AsyncClient) -> None:
    """Pagination params are validated: limit must be 1-100, offset >= 0."""
    token = await _signup_and_get_jwt(client, "pagination@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/dashboard/api-keys?limit=0", headers=headers)
    assert resp.status_code == 422

    resp = await client.get("/dashboard/api-keys?limit=101", headers=headers)
    assert resp.status_code == 422

    resp = await client.get("/dashboard/api-keys?offset=-1", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_rejects_when_limit_reached(client: AsyncClient) -> None:
    """Creating more than MAX_KEYS_PER_ORG active keys returns 422."""
    from unittest.mock import patch

    token = await _signup_and_get_jwt(client, "keylimit@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("gateway.services.api_key_service.MAX_KEYS_PER_ORG", 3):
        for i in range(3):
            resp = await client.post(
                "/dashboard/api-keys",
                json={"environment": "test"},
                headers=headers,
            )
            assert resp.status_code == 201, f"Key {i+1} failed: {resp.text}"

        resp = await client.post(
            "/dashboard/api-keys",
            json={"environment": "test"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "Maximum" in resp.json()["error"]["message"]
