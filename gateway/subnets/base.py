import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import bittensor as bt
import structlog

from gateway.core.exceptions import (
    MinerInvalidResponseError,
    MinerTimeoutError,
)
from gateway.routing.selector import MinerSelector

logger = structlog.get_logger()


@dataclass
class AdapterConfig:
    netuid: int
    subnet_name: str
    timeout_seconds: int
    max_retries: int = 0  # MVP: no retries


class BaseAdapter(ABC):
    """Fat base class — handles miner selection, Dendrite query, response
    validation, sanitization. Concrete adapters provide only ~50 lines:
    to_synapse(), from_response(), sanitize_output(), get_config()."""

    @abstractmethod
    def to_synapse(self, request_data: dict[str, Any]) -> bt.Synapse:
        """Convert API request to subnet-specific Synapse."""
        ...

    @abstractmethod
    def from_response(
        self, synapse: bt.Synapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert miner's Synapse response to API response dict."""
        ...

    @abstractmethod
    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize miner response before returning to consumer."""
        ...

    @abstractmethod
    def get_config(self) -> AdapterConfig:
        """Return adapter configuration."""
        ...

    async def execute(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        miner_selector: MinerSelector,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Full request lifecycle. Returns (response_body, gateway_headers)."""
        config = self.get_config()
        start_time = time.monotonic()

        # 1. Select miner (raises SubnetUnavailableError if none)
        axon = miner_selector.select_miner(config.netuid)
        miner_uid = axon.hotkey[:8]  # Safe prefix for logging/headers

        # 2. Build synapse
        synapse = self.to_synapse(request_data)

        # 3. Query miner via Dendrite
        try:
            responses = await dendrite.forward(
                axons=[axon],
                synapse=synapse,
                timeout=config.timeout_seconds,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "dendrite_query_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                elapsed_ms=round(elapsed * 1000),
            )
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc

        if not responses:
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        response_synapse = responses[0]

        # 4. Validate response
        if response_synapse.is_timeout:
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        if not response_synapse.is_success:
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )

        # 5. Convert and sanitize
        response_data = self.from_response(response_synapse, request_data)
        response_data = self.sanitize_output(response_data)

        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 6. Gateway headers
        headers = {
            "X-TaoGateway-Miner-UID": miner_uid,
            "X-TaoGateway-Latency-Ms": str(elapsed_ms),
            "X-TaoGateway-Subnet": config.subnet_name,
        }

        return response_data, headers
