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
async def test_overview_returns_account_info(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "overview@example.com")
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "overview@example.com"
    assert data["tier"] == "free"
    assert "created_at" in data
    assert data["api_key_count"] == 0
    assert data["first_api_key_prefix"] is None


@pytest.mark.asyncio
async def test_overview_includes_subnets(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "subnets@example.com")
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    subnets = data["subnets"]
    assert len(subnets) == 3

    # Verify subnet names are human-readable, not SN IDs
    names = {s["name"] for s in subnets}
    assert "Text Generation" in names
    assert "Image Generation" in names
    assert "Code Generation" in names

    # Verify each subnet has rate limits
    for subnet in subnets:
        assert "rate_limits" in subnet
        limits = subnet["rate_limits"]
        assert "minute" in limits
        assert "day" in limits
        assert "month" in limits
        assert limits["minute"] > 0
        assert limits["day"] > 0
        assert limits["month"] > 0


@pytest.mark.asyncio
async def test_overview_includes_health_status(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "health@example.com")
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for subnet in data["subnets"]:
        assert subnet["status"] in ("healthy", "degraded", "unavailable")


@pytest.mark.asyncio
async def test_overview_rate_limits_per_subnet(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "ratelimits@example.com")
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    by_netuid = {s["netuid"]: s for s in data["subnets"]}

    # SN1: 10/min, 100/day, 1000/month
    assert by_netuid[1]["rate_limits"]["minute"] == 10
    assert by_netuid[1]["rate_limits"]["day"] == 100
    assert by_netuid[1]["rate_limits"]["month"] == 1000

    # SN19: 5/min, 50/day, 500/month
    assert by_netuid[19]["rate_limits"]["minute"] == 5
    assert by_netuid[19]["rate_limits"]["day"] == 50
    assert by_netuid[19]["rate_limits"]["month"] == 500

    # SN62: 10/min, 100/day, 1000/month
    assert by_netuid[62]["rate_limits"]["minute"] == 10
    assert by_netuid[62]["rate_limits"]["day"] == 100
    assert by_netuid[62]["rate_limits"]["month"] == 1000


@pytest.mark.asyncio
async def test_overview_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/dashboard/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_overview_key_count_and_prefix(client: AsyncClient) -> None:
    token = await _signup_and_get_jwt(client, "keycount@example.com")

    # Initially 0 keys
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.json()["api_key_count"] == 0
    assert response.json()["first_api_key_prefix"] is None

    # Create a key
    create_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    created_prefix = create_resp.json()["prefix"]

    # Now should have 1 key with prefix
    response = await client.get(
        "/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["api_key_count"] == 1
    assert data["first_api_key_prefix"] == created_prefix
