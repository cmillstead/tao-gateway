from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.core.exceptions import (
    MinerInvalidResponseError,
    MinerTimeoutError,
    SubnetUnavailableError,
)
from gateway.subnets.base import AdapterConfig, BaseAdapter


class FakeAdapter(BaseAdapter):
    """Concrete adapter for testing the base execute() flow."""

    def to_synapse(self, request_data: dict):
        synapse = MagicMock()
        synapse.roles = request_data.get("roles", [])
        synapse.messages = request_data.get("messages", [])
        return synapse

    def from_response(self, synapse, request_data: dict | None = None) -> dict:
        return {"result": synapse.completion}

    def sanitize_output(self, response_data: dict) -> dict:
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=1, subnet_name="test-sn", timeout_seconds=10
        )


@pytest.fixture
def fake_adapter():
    return FakeAdapter()


@pytest.fixture
def mock_axon():
    axon = MagicMock()
    axon.hotkey = "abcdef1234567890"
    return axon


@pytest.fixture
def mock_miner_selector(mock_axon):
    selector = MagicMock()
    selector.select_miner.return_value = mock_axon
    return selector


@pytest.fixture
def mock_dendrite():
    return AsyncMock()


def _make_success_synapse(completion: str = "Hello!"):
    synapse = MagicMock()
    synapse.completion = completion
    synapse.is_success = True
    synapse.is_timeout = False
    return synapse


def _make_timeout_synapse():
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = True
    return synapse


def _make_invalid_synapse():
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = False
    return synapse


class TestBaseAdapterExecute:
    @pytest.mark.asyncio
    async def test_successful_execute(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = [
            _make_success_synapse("Hi there")
        ]

        response, headers = await fake_adapter.execute(
            request_data={"roles": ["user"], "messages": ["Hello"]},
            dendrite=mock_dendrite,
            miner_selector=mock_miner_selector,
        )

        assert response == {"result": "Hi there"}
        assert "X-TaoGateway-Miner-UID" in headers
        assert "X-TaoGateway-Latency-Ms" in headers
        assert headers["X-TaoGateway-Subnet"] == "test-sn"
        mock_miner_selector.select_miner.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_miner_uid_header_is_hotkey_prefix(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = [_make_success_synapse()]

        _, headers = await fake_adapter.execute(
            request_data={},
            dendrite=mock_dendrite,
            miner_selector=mock_miner_selector,
        )

        assert headers["X-TaoGateway-Miner-UID"] == "abcdef12"

    @pytest.mark.asyncio
    async def test_timeout_raises_miner_timeout_error(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = [_make_timeout_synapse()]

        with pytest.raises(MinerTimeoutError) as exc_info:
            await fake_adapter.execute(
                request_data={},
                dendrite=mock_dendrite,
                miner_selector=mock_miner_selector,
            )

        assert exc_info.value.status_code == 504
        assert exc_info.value.miner_uid == "abcdef12"
        assert exc_info.value.subnet == "test-sn"

    @pytest.mark.asyncio
    async def test_invalid_response_raises_error(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = [_make_invalid_synapse()]

        with pytest.raises(MinerInvalidResponseError) as exc_info:
            await fake_adapter.execute(
                request_data={},
                dendrite=mock_dendrite,
                miner_selector=mock_miner_selector,
            )

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_dendrite_exception_raises_timeout_error(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.side_effect = Exception("Network error")

        with pytest.raises(MinerTimeoutError):
            await fake_adapter.execute(
                request_data={},
                dendrite=mock_dendrite,
                miner_selector=mock_miner_selector,
            )

    @pytest.mark.asyncio
    async def test_no_miners_raises_subnet_unavailable(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_miner_selector.select_miner.side_effect = (
            SubnetUnavailableError("sn1")
        )

        with pytest.raises(SubnetUnavailableError) as exc_info:
            await fake_adapter.execute(
                request_data={},
                dendrite=mock_dendrite,
                miner_selector=mock_miner_selector,
            )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_empty_response_raises_invalid_response(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = []

        with pytest.raises(MinerInvalidResponseError) as exc_info:
            await fake_adapter.execute(
                request_data={},
                dendrite=mock_dendrite,
                miner_selector=mock_miner_selector,
            )

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_latency_header_is_numeric(
        self, fake_adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = [_make_success_synapse()]

        _, headers = await fake_adapter.execute(
            request_data={},
            dendrite=mock_dendrite,
            miner_selector=mock_miner_selector,
        )

        assert headers["X-TaoGateway-Latency-Ms"].isdigit()
