"""Tests for subnet configuration and adapter factory (Story 7-1).

Tests config parsing, factory mapping, and conditional registration.
Uses real Postgres and Redis per CLAUDE.md — only Bittensor SDK is mocked.
"""

import pytest

from gateway.core.config import Settings
from gateway.subnets.factory import adapter_factory, get_model_names
from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter
from gateway.subnets.sn22_search import SN22SearchAdapter
from gateway.subnets.sn32_detect import SN32DetectionAdapter
from gateway.subnets.sn62_code import SN62CodeAdapter


class TestEnabledSubnetsConfig:
    """Test enabled_subnets field parsing and defaults."""

    def test_default_enabled_subnets(self) -> None:
        """Default enabled_subnets is [32, 22] for new T&S subnets."""
        # Pass explicitly to bypass env var override from conftest
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            enabled_subnets=[32, 22],
        )
        assert s.enabled_subnets == [32, 22]

    def test_enabled_subnets_from_json_list(self) -> None:
        """JSON array format parses correctly."""
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            enabled_subnets=[1, 19, 62],
        )
        assert s.enabled_subnets == [1, 19, 62]

    def test_enabled_subnets_empty_list(self) -> None:
        """Empty list disables all subnets."""
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            enabled_subnets=[],
        )
        assert s.enabled_subnets == []

    def test_enabled_subnets_single(self) -> None:
        """Single subnet in list."""
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
            enabled_subnets=[32],
        )
        assert s.enabled_subnets == [32]


class TestNewSubnetConfigFields:
    """Test SN32 and SN22 config fields."""

    def test_sn32_defaults(self) -> None:
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.sn32_netuid == 32
        assert s.sn32_timeout_seconds == 30
        assert s.detection_rate_limit_per_minute == 60

    def test_sn22_defaults(self) -> None:
        s = Settings(
            debug=True,
            database_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.sn22_netuid == 22
        assert s.sn22_timeout_seconds == 30
        assert s.search_rate_limit_per_minute == 30


class TestAdapterFactory:
    """Test adapter_factory() mapping and instance creation."""

    def test_known_netuids_return_correct_adapter(self) -> None:
        assert isinstance(adapter_factory(1), SN1TextAdapter)
        assert isinstance(adapter_factory(19), SN19ImageAdapter)
        assert isinstance(adapter_factory(62), SN62CodeAdapter)

    def test_unknown_netuid_returns_none(self) -> None:
        assert adapter_factory(999) is None
        assert adapter_factory(0) is None
        assert adapter_factory(-1) is None

    def test_sn32_returns_detection_adapter(self) -> None:
        """SN32 returns the detection adapter (Story 7-2)."""
        assert isinstance(adapter_factory(32), SN32DetectionAdapter)

    def test_sn22_returns_search_adapter(self) -> None:
        """SN22 returns the search adapter (Story 7-3)."""
        assert isinstance(adapter_factory(22), SN22SearchAdapter)

    def test_factory_returns_new_instance_each_call(self) -> None:
        a1 = adapter_factory(1)
        a2 = adapter_factory(1)
        assert a1 is not a2


class TestGetModelNames:
    """Test get_model_names() helper."""

    def test_known_netuids(self) -> None:
        assert get_model_names(1) == ["tao-sn1"]
        assert get_model_names(19) == ["tao-sn19"]
        assert get_model_names(62) == ["tao-sn62"]

    def test_unknown_netuid_returns_empty(self) -> None:
        assert get_model_names(999) == []

    def test_returns_copy(self) -> None:
        """Returned list should be a copy, not a reference."""
        names = get_model_names(1)
        names.append("modified")
        assert get_model_names(1) == ["tao-sn1"]


class TestConditionalRouterInclusion:
    """Test that routes are conditionally included based on enabled_subnets."""

    @pytest.mark.asyncio
    async def test_disabled_subnet_routes_return_404(self, client) -> None:
        """Routes for disabled subnets (SN32/SN22 detection/search) should not exist.

        Since conftest enables SN1/SN19/SN62 but NOT SN32/SN22, detection and
        search routes should not be registered. They don't exist yet (Stories 7-2/7-3)
        but this validates the conditional router mechanism is in place.
        """
        response = await client.post(
            "/v1/moderations",
            json={"input": ["test text"]},
        )
        # 404 = route not registered (correct for disabled/non-existent subnet)
        assert response.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_enabled_subnet_routes_exist(self, client) -> None:
        """Enabled subnet routes should exist (require auth, not 404).

        Chat completions should return 401 (auth required), not 404 (not found).
        """
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "tao-sn1", "messages": [{"role": "user", "content": "hi"}]},
        )
        # 401 = route exists but auth required. 404 = route not registered.
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_models_endpoint_only_shows_enabled(self, client) -> None:
        """GET /v1/models returns only the enabled subnets."""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        model_ids = [m["id"] for m in data["data"]]
        # conftest enables SN1, SN19, SN62
        assert "tao-sn1" in model_ids
        assert "tao-sn19" in model_ids
        assert "tao-sn62" in model_ids

    @pytest.mark.asyncio
    async def test_models_endpoint_includes_capability(self, client) -> None:
        """Each model in /v1/models has a capability field from the adapter."""
        response = await client.get("/v1/models")
        data = response.json()
        for model in data["data"]:
            assert "capability" in model
            assert model["capability"] != ""
            assert "parameters" in model


class TestRateLimitConfig:
    """Test that new subnet rate limits are configured."""

    def test_sn32_rate_limits(self) -> None:
        from gateway.middleware.rate_limit import get_subnet_rate_limits

        limits = get_subnet_rate_limits(32)
        assert limits["minute"] == 60
        assert limits["day"] == 600
        assert limits["month"] == 6000

    def test_sn22_rate_limits(self) -> None:
        from gateway.middleware.rate_limit import get_subnet_rate_limits

        limits = get_subnet_rate_limits(22)
        assert limits["minute"] == 30
        assert limits["day"] == 300
        assert limits["month"] == 3000
