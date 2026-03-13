from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from gateway.core.database import engine
from gateway.main import app
from gateway.services.auth_service import create_jwt_token


@pytest.fixture(scope="session", autouse=True)
async def _clean_db_at_start() -> AsyncGenerator[None, None]:
    """Truncate all data tables at the start of test session for isolation."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE api_keys, organizations CASCADE"))
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def jwt_token() -> str:
    """Create a JWT token for a test org ID."""
    return create_jwt_token("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def auth_headers(jwt_token: str) -> dict[str, str]:
    """Headers with JWT auth for dashboard endpoints."""
    return {"Authorization": f"Bearer {jwt_token}"}
