import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_creates_account(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/signup",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["message"] == "Account created successfully"
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_409(client: AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "securepassword123"},
    )
    response = await client.post(
        "/auth/signup",
        json={"email": "dupe@example.com", "password": "anotherpassword123"},
    )
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["type"] == "conflict"


@pytest.mark.asyncio
async def test_signup_short_password_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/signup",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_email_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/signup",
        json={"email": "not-an-email", "password": "securepassword123"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_jwt(client: AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "securepassword123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"email": "wrongpw@example.com", "password": "securepassword123"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrongpassword123"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["type"] == "authentication_error"


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 401
