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


@pytest.mark.asyncio
async def test_health_includes_metagraph_status(client: AsyncClient) -> None:
    """Health endpoint includes metagraph sync status."""
    from gateway.api.health import clear_health_cache

    clear_health_cache()
    response = await client.get("/v1/health")
    data = response.json()
    assert "metagraph" in data
    assert "sn1" in data["metagraph"]
    sn1 = data["metagraph"]["sn1"]
    assert "netuid" in sn1
    assert "is_stale" in sn1


@pytest.mark.asyncio
async def test_health_ok_without_metagraph_manager(client: AsyncClient) -> None:
    """Health endpoint works when metagraph_manager is absent from app.state."""
    from gateway.api.health import clear_health_cache
    from gateway.main import app

    clear_health_cache()
    original = app.state.metagraph_manager
    del app.state.metagraph_manager
    try:
        response = await client.get("/v1/health")
        data = response.json()
        assert response.status_code == 200
        assert data["metagraph"] is None
    finally:
        app.state.metagraph_manager = original
        clear_health_cache()


@pytest.mark.asyncio
async def test_health_degraded_when_metagraph_stale(client: AsyncClient) -> None:
    """Health endpoint returns degraded when metagraph is stale."""
    from gateway.api.health import clear_health_cache
    from gateway.main import app

    clear_health_cache()

    # Make the metagraph stale
    mgr = app.state.metagraph_manager
    state = mgr.get_state(settings.sn1_netuid)
    if state:
        original_time = state.last_sync_time
        state.last_sync_time = 0.0  # force stale

    try:
        response = await client.get("/v1/health")
        data = response.json()
        assert response.status_code == 503
        assert data["status"] == "degraded"
        sn1 = data["metagraph"]["sn1"]
        assert sn1["is_stale"] is True
    finally:
        if state:
            state.last_sync_time = original_time
        clear_health_cache()
