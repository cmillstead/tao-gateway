import os

# Point tests at the test database and enable debug mode BEFORE any gateway imports.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway_test")
os.environ.setdefault("DEBUG", "true")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from gateway.core.database import engine  # noqa: E402
from gateway.core.redis import get_redis  # noqa: E402
from gateway.main import app  # noqa: E402
from gateway.services.auth_service import create_jwt_token  # noqa: E402


async def _flush_test_state() -> None:
    """Truncate DB tables and flush Redis test keys."""
    redis = await get_redis()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE api_keys, organizations CASCADE"))
    async for key in redis.scan_iter("auth_rate:*"):
        await redis.delete(key)
    async for key in redis.scan_iter("api_key:*"):
        await redis.delete(key)


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncGenerator[None, None]:
    """Truncate DB tables and flush Redis test keys before and after each test."""
    await _flush_test_state()
    yield
    await _flush_test_state()


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
