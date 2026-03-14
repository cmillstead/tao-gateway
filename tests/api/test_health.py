from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from gateway.api.health import clear_health_cache
from gateway.core.config import settings
from gateway.main import app


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_health_response_has_required_fields(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "database" in data
        assert "redis" in data
        assert "subnets" in data

    async def test_health_version_matches_settings(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        data = response.json()
        assert data["version"] == settings.app_version

    async def test_health_uptime_is_positive(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        data = response.json()
        assert data["uptime_seconds"] >= 0

    async def test_health_subnets_present(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        data = response.json()
        subnet_keys = set(data["subnets"].keys())
        assert subnet_keys == {"sn1", "sn19", "sn62"}

    async def test_subnet_health_has_required_fields(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        for _key, subnet in response.json()["subnets"].items():
            assert "netuid" in subnet
            assert "subnet_name" in subnet
            assert "status" in subnet
            assert subnet["status"] in ("healthy", "degraded", "unavailable")
            assert "neuron_count" in subnet
            assert "last_sync" in subnet
            assert "is_stale" in subnet

    async def test_subnet_healthy_when_synced(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        for subnet in response.json()["subnets"].values():
            assert subnet["status"] == "healthy"
            assert subnet["is_stale"] is False
            assert subnet["last_sync"] is not None

    async def test_subnet_neuron_count_included(self, client: AsyncClient) -> None:
        response = await client.get("/v1/health")
        for subnet in response.json()["subnets"].values():
            assert subnet["neuron_count"] is not None

    async def test_degraded_when_db_down(self, client: AsyncClient) -> None:
        clear_health_cache()
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionError("DB down")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = lambda: mock_session  # noqa: E731

        with patch("gateway.api.health.get_session_factory", return_value=mock_factory):
            try:
                response = await client.get("/v1/health")
                data = response.json()
                assert response.status_code == 503
                assert data["status"] == "degraded"
                assert data["database"] == "unhealthy"
            finally:
                clear_health_cache()

    async def test_degraded_when_redis_down(self, client: AsyncClient) -> None:
        clear_health_cache()
        with patch("gateway.api.health.try_get_redis", return_value=None):
            response = await client.get("/v1/health")
            data = response.json()
            assert response.status_code == 503
            assert data["status"] == "degraded"
            assert data["redis"] == "unhealthy"
        clear_health_cache()

    async def test_degraded_when_metagraph_stale(self, client: AsyncClient) -> None:
        clear_health_cache()
        mgr = app.state.metagraph_manager
        state = mgr.get_state(settings.sn1_netuid)
        assert state is not None
        original_time = state.last_sync_time
        original_mono = state.last_sync_mono
        state.last_sync_time = 0.0  # force stale
        state.last_sync_mono = -1.0

        try:
            response = await client.get("/v1/health")
            data = response.json()
            assert response.status_code == 503
            assert data["status"] == "degraded"
            # SN1 should show degraded, others healthy
            assert data["subnets"]["sn1"]["is_stale"] is True
            assert data["subnets"]["sn1"]["status"] == "degraded"
            assert data["subnets"]["sn19"]["is_stale"] is False
            assert data["subnets"]["sn19"]["status"] == "healthy"
        finally:
            state.last_sync_time = original_time
            state.last_sync_mono = original_mono
            clear_health_cache()

    async def test_subnet_unavailable_when_no_metagraph(
        self, client: AsyncClient
    ) -> None:
        clear_health_cache()
        mgr = app.state.metagraph_manager
        state = mgr.get_state(settings.sn62_netuid)
        assert state is not None
        original_mg = state.metagraph
        original_time = state.last_sync_time
        original_mono = state.last_sync_mono
        state.metagraph = None
        state.last_sync_time = 0.0
        state.last_sync_mono = -1.0

        try:
            response = await client.get("/v1/health")
            data = response.json()
            assert data["subnets"]["sn62"]["status"] == "unavailable"
            assert data["subnets"]["sn62"]["neuron_count"] is None
        finally:
            state.metagraph = original_mg
            state.last_sync_time = original_time
            state.last_sync_mono = original_mono
            clear_health_cache()

    async def test_each_subnet_reported_independently(
        self, client: AsyncClient
    ) -> None:
        clear_health_cache()
        mgr = app.state.metagraph_manager
        # Make SN19 stale, keep others healthy
        sn19_state = mgr.get_state(19)
        assert sn19_state is not None
        original_time = sn19_state.last_sync_time
        original_mono = sn19_state.last_sync_mono
        sn19_state.last_sync_time = 0.0
        sn19_state.last_sync_mono = -1.0

        try:
            response = await client.get("/v1/health")
            subnets = response.json()["subnets"]
            assert subnets["sn1"]["status"] == "healthy"
            assert subnets["sn19"]["status"] == "degraded"
            assert subnets["sn62"]["status"] == "healthy"
        finally:
            sn19_state.last_sync_time = original_time
            sn19_state.last_sync_mono = original_mono
            clear_health_cache()

    async def test_cache_serves_cached_response(self, client: AsyncClient) -> None:
        resp1 = await client.get("/v1/health")
        assert resp1.status_code == 200
        resp2 = await client.get("/v1/health")
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()


@pytest.mark.asyncio
async def test_docs_accessible(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redoc_accessible(client: AsyncClient) -> None:
    response = await client.get("/redoc")
    assert response.status_code == 200
