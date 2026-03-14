"""Verify all adapters follow the fat-base / thin-adapter structural pattern."""

import pytest

from gateway.subnets import ADAPTER_DEFINITIONS
from gateway.subnets.base import AdapterConfig, BaseAdapter
from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter
from gateway.subnets.sn62_code import SN62CodeAdapter

ALL_ADAPTERS = [cls for cls, _names, _attr in ADAPTER_DEFINITIONS]


class TestAdapterPattern:
    @pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
    def test_is_base_adapter_subclass(self, adapter_cls):
        assert issubclass(adapter_cls, BaseAdapter)

    @pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
    def test_get_config_returns_adapter_config(self, adapter_cls):
        adapter = adapter_cls()
        config = adapter.get_config()
        assert isinstance(config, AdapterConfig)
        assert config.netuid > 0
        assert len(config.subnet_name) > 0
        assert config.timeout_seconds > 0

    @pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
    def test_get_capability_returns_non_empty_string(self, adapter_cls):
        adapter = adapter_cls()
        capability = adapter.get_capability()
        assert isinstance(capability, str)
        assert len(capability) > 0

    @pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
    def test_get_parameters_returns_non_empty_dict(self, adapter_cls):
        adapter = adapter_cls()
        params = adapter.get_parameters()
        assert isinstance(params, dict)
        assert len(params) > 0
        for key, value in params.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_no_duplicate_netuids(self):
        netuids = [cls().get_config().netuid for cls in ALL_ADAPTERS]
        assert len(netuids) == len(set(netuids))

    def test_no_duplicate_subnet_names(self):
        names = [cls().get_config().subnet_name for cls in ALL_ADAPTERS]
        assert len(names) == len(set(names))

    def test_sn1_supports_streaming(self):
        adapter = SN1TextAdapter()
        assert hasattr(adapter, "to_streaming_synapse")
        assert hasattr(adapter, "format_stream_chunk")
        assert hasattr(adapter, "format_stream_done")

    def test_sn19_no_streaming(self):
        adapter = SN19ImageAdapter()
        with pytest.raises(NotImplementedError):
            adapter.to_streaming_synapse({})

    def test_sn62_no_streaming(self):
        adapter = SN62CodeAdapter()
        with pytest.raises(NotImplementedError):
            adapter.to_streaming_synapse({})
