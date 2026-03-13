import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

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


@pytest.fixture
def adapter():
    return FakeStreamAdapter()


@pytest.fixture
def mock_axon():
    axon = MagicMock()
    axon.hotkey = "abcdef1234567890"
    return axon


@pytest.fixture
def mock_dendrite():
    return AsyncMock()


def _stream_kwargs(adapter, mock_dendrite, mock_axon, **extra):
    """Build common kwargs for execute_stream calls."""
    return {
        "dendrite": mock_dendrite,
        "axon": mock_axon,
        "miner_uid": mock_axon.hotkey[:8],
        **extra,
    }


class TestExecuteStream:
    @pytest.mark.asyncio
    async def test_yields_chunks_and_done(
        self, adapter, mock_dendrite, mock_axon
    ):
        async def _stream():
            yield "Hello"
            yield " world"

        mock_dendrite.forward.return_value = [_stream()]

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert "Hello" in text
        assert "world" in text
        assert "data: [DONE]" in text
        assert "chat.completion.chunk" in text

    @pytest.mark.asyncio
    async def test_includes_ttft_comment(
        self, adapter, mock_dendrite, mock_axon
    ):
        async def _stream():
            yield "token"

        mock_dendrite.forward.return_value = [_stream()]

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert ": ttft_ms=" in text

    @pytest.mark.asyncio
    async def test_first_chunk_includes_role(
        self, adapter, mock_dendrite, mock_axon
    ):
        async def _stream():
            yield "Hello"
            yield " world"

        mock_dendrite.forward.return_value = [_stream()]

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        # First data chunk should have role
        data_chunks = [c for c in chunks if c.startswith("data: {")]
        first_data = json.loads(data_chunks[0][6:].strip())
        assert first_data["choices"][0]["delta"].get("role") == "assistant"

        # Second data chunk should NOT have role
        second_data = json.loads(data_chunks[1][6:].strip())
        assert "role" not in second_data["choices"][0]["delta"]

    @pytest.mark.asyncio
    async def test_timeout_mid_stream_no_stop_chunk(
        self, adapter, mock_dendrite, mock_axon
    ):
        async def _stream():
            yield "partial"
            raise TimeoutError("timeout")

        mock_dendrite.forward.return_value = [_stream()]

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert "gateway_timeout" in text
        assert "data: [DONE]" in text
        # Should NOT have a stop chunk with finish_reason after error
        assert '"finish_reason": "stop"' not in text

    @pytest.mark.asyncio
    async def test_dendrite_forward_timeout(
        self, adapter, mock_dendrite, mock_axon
    ):
        mock_dendrite.forward.side_effect = TimeoutError("connection timeout")

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert "gateway_timeout" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_dendrite_forward_error(
        self, adapter, mock_dendrite, mock_axon
    ):
        mock_dendrite.forward.side_effect = ConnectionError("network error")

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert "bad_gateway" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_empty_response(
        self, adapter, mock_dendrite, mock_axon
    ):
        mock_dendrite.forward.return_value = []

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
        ):
            chunks.append(chunk)

        text = "".join(chunks)
        assert "bad_gateway" in text
        assert "data: [DONE]" in text

    @pytest.mark.asyncio
    async def test_client_disconnect(
        self, adapter, mock_dendrite, mock_axon
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

        chunks = []
        async for chunk in adapter.execute_stream(
            request_data={"model": "test"},
            **_stream_kwargs(adapter, mock_dendrite, mock_axon),
            is_disconnected=_is_disconnected,
        ):
            chunks.append(chunk)
            if "delta" in chunk:
                chunk_count += 1

        text = "".join(chunks)
        assert "token1" in text
