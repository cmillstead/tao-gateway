import pytest

from gateway.core.exceptions import SubnetUnavailableError
from gateway.subnets.base import AdapterConfig, BaseAdapter
from gateway.subnets.registry import AdapterRegistry


class StubAdapter(BaseAdapter):
    def __init__(self, netuid: int, name: str):
        self._netuid = netuid
        self._name = name

    def to_synapse(self, request_data: dict):
        pass

    def from_response(self, synapse, request_data: dict | None = None) -> dict:
        return {}

    def sanitize_output(self, response_data: dict) -> dict:
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(netuid=self._netuid, subnet_name=self._name, timeout_seconds=10)


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
