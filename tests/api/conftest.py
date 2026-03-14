from httpx import AsyncClient


async def get_api_key(client: AsyncClient, email: str) -> str:
    """Signup + login + create API key. Returns the raw key string."""
    await client.post(
        "/auth/signup",
        json={"email": email, "password": "securepassword123"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    jwt = login_resp.json()["access_token"]
    key_resp = await client.post(
        "/dashboard/api-keys",
        json={"environment": "live"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    return key_resp.json()["key"]
