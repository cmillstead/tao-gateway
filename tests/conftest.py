from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]
