import os

# Point tests at the test database BEFORE any gateway imports.
# This overrides the default in gateway.core.config.Settings.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway_test")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from gateway.core.database import engine  # noqa: E402
from gateway.core.redis import get_redis  # noqa: E402
from gateway.main import app  # noqa: E402
from gateway.services.auth_service import create_jwt_token  # noqa: E402


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncGenerator[None, None]:
    """Truncate DB tables and flush Redis rate limit keys before and after each test."""
    redis = await get_redis()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE api_keys, organizations CASCADE"))
    for key in await redis.keys("auth_rate:*"):
        await redis.delete(key)
    for key in await redis.keys("api_key:*"):
        await redis.delete(key)
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE api_keys, organizations CASCADE"))
    for key in await redis.keys("auth_rate:*"):
        await redis.delete(key)
    for key in await redis.keys("api_key:*"):
        await redis.delete(key)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def jwt_token() -> str:
    """Create a JWT for a non-existent org — JWT validation tests only."""
    return create_jwt_token("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def auth_headers(jwt_token: str) -> dict[str, str]:
    """Headers with JWT auth for dashboard endpoints (non-existent org — JWT validation only)."""
    return {"Authorization": f"Bearer {jwt_token}"}
