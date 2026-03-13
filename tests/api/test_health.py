import pytest
from httpx import AsyncClient

from gateway.core.config import settings


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.app_version
    assert data["database"] == "healthy"
    assert data["redis"] == "healthy"


@pytest.mark.asyncio
async def test_docs_accessible(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redoc_accessible(client: AsyncClient) -> None:
    response = await client.get("/redoc")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_degraded_when_db_down(client: AsyncClient) -> None:
    """Health endpoint returns 503 with degraded status when DB is down."""
    from unittest.mock import AsyncMock

    from gateway.api.health import clear_health_cache

    clear_health_cache()

    # Override the dependency at the app level to inject a broken DB session
    from gateway.core.database import get_db
    from gateway.main import app

    mock_session = AsyncMock()
    mock_session.execute.side_effect = ConnectionError("DB down")

    async def _broken_db():  # type: ignore[no-untyped-def]
        yield mock_session

    app.dependency_overrides[get_db] = _broken_db
    try:
        response = await client.get("/v1/health")
        data = response.json()
        assert response.status_code == 503
        assert data["status"] == "degraded"
        assert data["database"] == "unhealthy"
    finally:
        app.dependency_overrides.pop(get_db, None)
        clear_health_cache()


@pytest.mark.asyncio
async def test_health_cache_serves_cached_response(client: AsyncClient) -> None:
    """Second health request within TTL returns cached result."""
    resp1 = await client.get("/v1/health")
    assert resp1.status_code == 200
    resp2 = await client.get("/v1/health")
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()
