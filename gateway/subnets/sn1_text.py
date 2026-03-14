import json
import time
from collections.abc import AsyncIterator
from typing import Any

import bittensor as bt

from gateway.core.config import settings
from gateway.subnets.base import AdapterConfig, BaseAdapter, generate_completion_id


class TextGenSynapse(bt.Synapse):  # type: ignore[misc]
    """SN1 text generation synapse. Miners expect parallel role/message arrays."""

    roles: list[str] = []
    messages: list[str] = []
    completion: str = ""
    required_hash_fields: list[str] = ["roles", "messages"]


class TextGenStreamingSynapse(bt.StreamingSynapse):  # type: ignore[misc]
    """SN1 streaming text generation synapse."""

    roles: list[str] = []
    messages: list[str] = []
    completion: str = ""
    required_hash_fields: list[str] = ["roles", "messages"]

    async def process_streaming_response(self, response: Any) -> AsyncIterator[str]:
        """Yield text chunks from the miner's streaming HTTP response."""
        async for chunk in response.content.iter_any():
            decoded = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            if decoded:
                self.completion += decoded
                yield decoded

    def extract_response_json(self, response: Any) -> dict[str, Any]:
        """Extract accumulated completion from the stream."""
        return {"completion": self.completion}


def _extract_messages(request_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract parallel role/message arrays from OpenAI chat format."""
    messages = request_data["messages"]
    for m in messages:
        if not isinstance(m["content"], str):
            raise ValueError(
                "Multimodal content is not supported for text generation. "
                "Content must be a string."
            )
    return [m["role"] for m in messages], [m["content"] for m in messages]


class SN1TextAdapter(BaseAdapter):
    """Thin adapter: OpenAI chat format <-> TextGenSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> TextGenSynapse:
        roles, messages = _extract_messages(request_data)
        return TextGenSynapse(roles=roles, messages=messages)

    def from_response(
        self, synapse: TextGenSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": generate_completion_id(),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": str(request_data.get("model", "tao-sn1")),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": synapse.completion,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        content = response_data["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        response_data["choices"][0]["message"]["content"] = self.sanitize_text(content)
        return response_data

    def to_streaming_synapse(
        self, request_data: dict[str, Any]
    ) -> TextGenStreamingSynapse:
        roles, messages = _extract_messages(request_data)
        return TextGenStreamingSynapse(roles=roles, messages=messages)

    def format_stream_chunk(
        self, chunk: str, chunk_id: str, model: str, created: int,
        *, include_role: bool = False,
    ) -> str:
        """Format a raw text chunk as an OpenAI-compatible SSE data line."""
        content = self.sanitize_text(chunk)
        delta: dict[str, str | None] = {"content": content}
        if include_role:
            delta["role"] = "assistant"
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": None,
                }
            ],
        }
        return f"data: {json.dumps(data)}\n\n"

    def format_stream_done(
        self, chunk_id: str, model: str, created: int
    ) -> str:
        """Format the final stop chunk and [DONE] terminator."""
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        return f"data: {json.dumps(data)}\n\ndata: [DONE]\n\n"

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn1_netuid,
            subnet_name="sn1",
            timeout_seconds=settings.dendrite_timeout_seconds,
        )
