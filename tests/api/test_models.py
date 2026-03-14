from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestListModels:
    async def test_returns_all_registered_subnets(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 3

    async def test_each_model_has_required_fields(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        for model in resp.json()["data"]:
            assert "id" in model
            assert model["object"] == "model"
            assert "created" in model
            assert model["owned_by"] == "tao-gateway"
            assert "subnet_id" in model
            assert "capability" in model
            assert model["status"] in ("available", "unavailable")
            assert "parameters" in model

    async def test_subnet_ids_are_correct(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        subnet_ids = {m["subnet_id"] for m in resp.json()["data"]}
        assert subnet_ids == {1, 19, 62}

    async def test_model_ids_match_registered_names(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        model_ids = {m["id"] for m in resp.json()["data"]}
        assert model_ids == {"tao-sn1", "tao-sn19", "tao-sn62"}

    async def test_capabilities_are_correct(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        caps = {m["subnet_id"]: m["capability"] for m in resp.json()["data"]}
        assert caps[1] == "Text Generation"
        assert caps[19] == "Image Generation"
        assert caps[62] == "Code Generation"

    async def test_no_auth_required(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        assert resp.status_code == 200

    async def test_parameters_present_for_each_subnet(self, client: AsyncClient):
        resp = await client.get("/v1/models")
        for model in resp.json()["data"]:
            assert isinstance(model["parameters"], dict)
            assert len(model["parameters"]) > 0

    async def test_status_unavailable_when_no_neurons(
        self, client: AsyncClient, test_app
    ):
        """When metagraph has n=0, status should be unavailable."""
        mgr = test_app.state.metagraph_manager
        for netuid in (1, 19, 62):
            state = mgr.get_state(netuid)
            mg = MagicMock()
            mg.n = 0
            state.metagraph = mg

        resp = await client.get("/v1/models")
        for model in resp.json()["data"]:
            assert model["status"] == "unavailable"

    async def test_status_available_when_neurons_exist(
        self, client: AsyncClient, test_app
    ):
        """When metagraph has neurons, status should be available."""
        mgr = test_app.state.metagraph_manager
        for netuid in (1, 19, 62):
            state = mgr.get_state(netuid)
            mg = MagicMock()
            mg.n = 256
            state.metagraph = mg

        resp = await client.get("/v1/models")
        for model in resp.json()["data"]:
            assert model["status"] == "available"

    async def test_mixed_availability(self, client: AsyncClient, test_app):
        """Some subnets available, others not."""
        mgr = test_app.state.metagraph_manager
        # SN1 has neurons
        sn1_state = mgr.get_state(1)
        mg = MagicMock()
        mg.n = 100
        sn1_state.metagraph = mg
        # SN19 has no metagraph
        sn19_state = mgr.get_state(19)
        sn19_state.metagraph = None

        resp = await client.get("/v1/models")
        by_id = {m["subnet_id"]: m for m in resp.json()["data"]}
        assert by_id[1]["status"] == "available"
        assert by_id[19]["status"] == "unavailable"

    async def test_empty_registry(self, client: AsyncClient, test_app):
        """Empty adapter registry returns empty list."""
        from gateway.subnets.registry import AdapterRegistry
        test_app.state.adapter_registry = AdapterRegistry()

        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_works_without_metagraph_manager(
        self, client: AsyncClient, test_app
    ):
        """When Bittensor is disabled, metagraph_manager is absent."""
        original = test_app.state.metagraph_manager
        del test_app.state.metagraph_manager

        try:
            resp = await client.get("/v1/models")
            assert resp.status_code == 200
            # All subnets should show as unavailable
            for model in resp.json()["data"]:
                assert model["status"] == "unavailable"
        finally:
            test_app.state.metagraph_manager = original

    async def test_capabilities_from_adapter_self_description(
        self, client: AsyncClient
    ):
        """Capabilities come from adapter.get_capability(), not hardcoded maps."""
        from gateway.subnets.sn1_text import SN1TextAdapter
        from gateway.subnets.sn19_image import SN19ImageAdapter
        from gateway.subnets.sn62_code import SN62CodeAdapter

        expected = {
            1: SN1TextAdapter().get_capability(),
            19: SN19ImageAdapter().get_capability(),
            62: SN62CodeAdapter().get_capability(),
        }
        resp = await client.get("/v1/models")
        for model in resp.json()["data"]:
            assert model["capability"] == expected[model["subnet_id"]]

    async def test_dynamic_adapter_appears_in_models(
        self, client: AsyncClient, test_app
    ):
        """A dynamically registered adapter auto-appears in /v1/models."""
        from tests.subnets.test_registry import StubAdapter

        registry = test_app.state.adapter_registry
        stub = StubAdapter(99, "sn99")
        registry.register(stub, model_names=["tao-sn99"])

        resp = await client.get("/v1/models")
        ids = {m["id"] for m in resp.json()["data"]}
        assert "tao-sn99" in ids
        sn99 = next(m for m in resp.json()["data"] if m["id"] == "tao-sn99")
        assert sn99["subnet_id"] == 99
        assert sn99["capability"] == "Test Capability"
        assert sn99["parameters"] == {"param": "string (required)"}
