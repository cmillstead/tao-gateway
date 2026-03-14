from dataclasses import dataclass, field

import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.subnets.base import AdapterConfig, BaseAdapter

logger = structlog.get_logger()


@dataclass
class AdapterInfo:
    """Public metadata about a registered adapter."""

    config: AdapterConfig
    model_names: list[str] = field(default_factory=list)
    adapter: BaseAdapter | None = None


class AdapterRegistry:
    """Maps netuids and model names to adapter instances."""

    def __init__(self) -> None:
        self._by_netuid: dict[int, BaseAdapter] = {}
        self._by_model: dict[str, BaseAdapter] = {}
        self._model_names: dict[int, list[str]] = {}

    def register(self, adapter: BaseAdapter, model_names: list[str] | None = None) -> None:
        config = adapter.get_config()
        self._by_netuid[config.netuid] = adapter
        self._model_names[config.netuid] = model_names or []
        if model_names:
            for name in model_names:
                self._by_model[name] = adapter
        logger.info("adapter_registered", subnet=config.subnet_name, netuid=config.netuid)

    def get(self, netuid: int) -> BaseAdapter:
        adapter = self._by_netuid.get(netuid)
        if adapter is None:
            raise SubnetUnavailableError(f"sn{netuid}")
        return adapter

    def get_by_model(self, model_name: str) -> BaseAdapter:
        adapter = self._by_model.get(model_name)
        if adapter is None:
            raise SubnetUnavailableError(
                model_name, reason=f"no adapter registered for model '{model_name}'"
            )
        return adapter

    def list_all(self) -> list[AdapterInfo]:
        """Return metadata for all registered adapters."""
        return [
            AdapterInfo(
                config=adapter.get_config(),
                model_names=list(self._model_names.get(netuid, [])),
                adapter=adapter,
            )
            for netuid, adapter in self._by_netuid.items()
        ]

    def get_all_netuids(self) -> list[int]:
        """Return all registered subnet netuids."""
        return list(self._by_netuid.keys())
