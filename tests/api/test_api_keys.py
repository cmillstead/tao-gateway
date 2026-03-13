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
    keys = response.json()
    assert len(keys) >= 1
    for key in keys:
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
