import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.core.constants import HDR_MINER_UID
from gateway.subnets.base import AdapterConfig, BaseAdapter
from gateway.subnets.sn1_text import TextGenStreamingSynapse


class FakeStreamAdapter(BaseAdapter):
    """Concrete adapter for testing the base execute_stream() flow."""

    def to_synapse(self, request_data: dict[str, Any]):
        return MagicMock()

    def from_response(self, synapse, request_data: dict[str, Any]) -> dict[str, Any]:
        return {}

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        return response_data

    def to_streaming_synapse(self, request_data: dict[str, Any]):
        return TextGenStreamingSynapse(
            roles=request_data.get("roles", []),
            messages=request_data.get("messages", []),
        )

    def format_stream_chunk(
        self, chunk: str, chunk_id: str, model: str, created: int,
        *, include_role: bool = False,
    ) -> str:
        delta: dict[str, str | None] = {"content": chunk}
        if include_role:
            delta["role"] = "assistant"
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        return f"data: {json.dumps(data)}\n\n"

    def format_stream_done(
        self, chunk_id: str, model: str, created: int
    ) -> str:
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        return f"data: {json.dumps(data)}\n\ndata: [DONE]\n\n"

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(netuid=1, subnet_name="test-sn", timeout_seconds=10)

    def get_capability(self) -> str:
        return "Test"

    def get_parameters(self) -> dict[str, str]:
        return {}


@pytest.fixture
def adapter():
    return FakeStreamAdapter()


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


def _stream_kwargs(adapter, mock_dendrite, mock_miner_selector, **extra):
    """Build common kwargs for execute_stream calls."""
    return {
        "dendrite": mock_dendrite,
        "miner_selector": mock_miner_selector,
        **extra,
    }


async def _collect_stream(adapter, request_data, mock_dendrite, mock_miner_selector, **extra):
    """Call execute_stream and collect all chunks from the generator."""
    headers, gen = await adapter.execute_stream(
        request_data=request_data,
        **_stream_kwargs(adapter, mock_dendrite, mock_miner_selector),
        **extra,
    )
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return headers, chunks


class TestExecuteStream:
    @pytest.mark.asyncio
    async def test_yields_chunks_and_done(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        async def _stream():
            yield "Hello"
            yield " world"

        mock_dendrite.forward.return_value = [_stream()]

        headers, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        assert HDR_MINER_UID in headers
        text = "".join(chunks)
        assert "Hello" in text
        assert "world" in text
        assert "data: [DONE]" in text
        assert "chat.completion.chunk" in text

    @pytest.mark.asyncio
    async def test_includes_ttft_comment(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        async def _stream():
            yield "token"

        mock_dendrite.forward.return_value = [_stream()]

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        assert ": ttft_ms=" in text

    @pytest.mark.asyncio
    async def test_first_chunk_includes_role(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        async def _stream():
            yield "Hello"
            yield " world"

        mock_dendrite.forward.return_value = [_stream()]

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        # First data chunk should have role
        data_chunks = [c for c in chunks if c.startswith("data: {")]
        first_data = json.loads(data_chunks[0][6:].strip())
        assert first_data["choices"][0]["delta"].get("role") == "assistant"

        # Second data chunk should NOT have role
        second_data = json.loads(data_chunks[1][6:].strip())
        assert "role" not in second_data["choices"][0]["delta"]

    @pytest.mark.asyncio
    async def test_timeout_mid_stream_no_stop_chunk(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        async def _stream():
            yield "partial"
            raise TimeoutError("timeout")

        mock_dendrite.forward.return_value = [_stream()]

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        assert "gateway_timeout" in text
        assert "data: [DONE]" in text
        assert '"finish_reason": "stop"' not in text

    @pytest.mark.asyncio
    async def test_dendrite_forward_timeout(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.side_effect = TimeoutError("connection timeout")

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        assert "gateway_timeout" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_dendrite_forward_error(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.side_effect = ConnectionError("network error")

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        assert "bad_gateway" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_empty_response(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        mock_dendrite.forward.return_value = []

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        assert "bad_gateway" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_sse_error_omits_miner_uid(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        """SEC-018: miner_uid must not leak to clients in SSE error payloads."""
        mock_dendrite.forward.side_effect = ConnectionError("network error")

        _, chunks = await _collect_stream(
            adapter, {"model": "test"}, mock_dendrite, mock_miner_selector,
        )

        text = "".join(chunks)
        # Error payload should exist but not contain miner_uid
        assert "bad_gateway" in text
        for chunk in chunks:
            if chunk.startswith("data: {"):
                payload = json.loads(chunk[6:].strip())
                if "error" in payload:
                    assert "miner_uid" not in payload["error"]

    @pytest.mark.asyncio
    async def test_client_disconnect(
        self, adapter, mock_dendrite, mock_miner_selector
    ):
        call_count = 0

        async def _stream():
            nonlocal call_count
            while True:
                call_count += 1
                yield f"token{call_count}"

        mock_dendrite.forward.return_value = [_stream()]

        disconnect_after = 1
        chunk_count = 0

        async def _is_disconnected():
            return chunk_count >= disconnect_after

        headers, gen = await adapter.execute_stream(
            request_data={"model": "test"},
            dendrite=mock_dendrite,
            miner_selector=mock_miner_selector,
            is_disconnected=_is_disconnected,
        )
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
            if "delta" in chunk:
                chunk_count += 1

        text = "".join(chunks)
        assert "token1" in text
