import structlog

from gateway.subnets.base import BaseAdapter

logger = structlog.get_logger()


class AdapterRegistry:
    """Maps netuids and model names to adapter instances."""

    def __init__(self) -> None:
        self._by_netuid: dict[int, BaseAdapter] = {}
        self._by_model: dict[str, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter, model_names: list[str] | None = None) -> None:
        config = adapter.get_config()
        self._by_netuid[config.netuid] = adapter
        if model_names:
            for name in model_names:
                self._by_model[name] = adapter
        logger.info("adapter_registered", subnet=config.subnet_name, netuid=config.netuid)

    def get(self, netuid: int) -> BaseAdapter:
        adapter = self._by_netuid.get(netuid)
        if adapter is None:
            from gateway.core.exceptions import SubnetUnavailableError

            raise SubnetUnavailableError(f"sn{netuid}")
        return adapter

    def get_by_model(self, model_name: str) -> BaseAdapter:
        adapter = self._by_model.get(model_name)
        if adapter is None:
            from gateway.core.exceptions import SubnetUnavailableError

            raise SubnetUnavailableError(model_name)
        return adapter
