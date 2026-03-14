from typing import Any

import pytest

from gateway.core.exceptions import SubnetUnavailableError
from gateway.subnets.base import AdapterConfig, BaseAdapter
from gateway.subnets.registry import AdapterInfo, AdapterRegistry


class StubAdapter(BaseAdapter):
    def __init__(self, netuid: int, name: str):
        self._netuid = netuid
        self._name = name

    def to_synapse(self, request_data: dict[str, Any]):
        pass

    def from_response(self, synapse, request_data: dict[str, Any]) -> dict[str, Any]:
        return {}

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(netuid=self._netuid, subnet_name=self._name, timeout_seconds=10)

    def get_capability(self) -> str:
        return "Test Capability"

    def get_parameters(self) -> dict[str, str]:
        return {"param": "string (required)"}


class TestAdapterRegistry:
    def test_register_and_get_by_netuid(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter)
        assert registry.get(1) is adapter

    def test_register_and_get_by_model(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1"])
        assert registry.get_by_model("tao-sn1") is adapter

    def test_get_unknown_netuid_raises(self):
        registry = AdapterRegistry()
        with pytest.raises(SubnetUnavailableError):
            registry.get(999)

    def test_get_unknown_model_raises(self):
        registry = AdapterRegistry()
        with pytest.raises(SubnetUnavailableError):
            registry.get_by_model("unknown-model")

    def test_multiple_model_names(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1", "sn1-text"])
        assert registry.get_by_model("tao-sn1") is adapter
        assert registry.get_by_model("sn1-text") is adapter


class TestAdapterRegistryListAll:
    def test_list_all_empty_registry(self):
        registry = AdapterRegistry()
        assert registry.list_all() == []

    def test_list_all_returns_all_registered(self):
        registry = AdapterRegistry()
        a1 = StubAdapter(1, "sn1")
        a2 = StubAdapter(19, "sn19")
        registry.register(a1, model_names=["tao-sn1"])
        registry.register(a2, model_names=["tao-sn19"])
        result = registry.list_all()
        assert len(result) == 2

    def test_list_all_preserves_model_names(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1"])
        result = registry.list_all()
        assert result[0].model_names == ["tao-sn1"]

    def test_list_all_returns_adapter_info(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(62, "sn62")
        registry.register(adapter, model_names=["tao-sn62"])
        result = registry.list_all()
        info = result[0]
        assert isinstance(info, AdapterInfo)
        assert info.config.netuid == 62
        assert info.config.subnet_name == "sn62"
        assert info.model_names == ["tao-sn62"]

    def test_list_all_with_no_model_names(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter)
        result = registry.list_all()
        assert result[0].model_names == []

    def test_list_all_with_multiple_model_names(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1", "gpt-3.5-turbo"])
        result = registry.list_all()
        assert result[0].model_names == ["tao-sn1", "gpt-3.5-turbo"]


class TestAdapterInfoAdapter:
    def test_adapter_info_exposes_adapter_instance(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1"])
        info = registry.list_all()[0]
        assert info.adapter is adapter

    def test_adapter_capability_accessible_via_info(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1"])
        info = registry.list_all()[0]
        assert info.adapter is not None
        assert info.adapter.get_capability() == "Test Capability"

    def test_adapter_parameters_accessible_via_info(self):
        registry = AdapterRegistry()
        adapter = StubAdapter(1, "sn1")
        registry.register(adapter, model_names=["tao-sn1"])
        info = registry.list_all()[0]
        assert info.adapter is not None
        assert info.adapter.get_parameters() == {"param": "string (required)"}


class TestAdapterRegistryGetAllNetuids:
    def test_get_all_netuids_empty(self):
        registry = AdapterRegistry()
        assert registry.get_all_netuids() == []

    def test_get_all_netuids_returns_all(self):
        registry = AdapterRegistry()
        registry.register(StubAdapter(1, "sn1"), model_names=["tao-sn1"])
        registry.register(StubAdapter(19, "sn19"), model_names=["tao-sn19"])
        registry.register(StubAdapter(62, "sn62"), model_names=["tao-sn62"])
        assert sorted(registry.get_all_netuids()) == [1, 19, 62]
