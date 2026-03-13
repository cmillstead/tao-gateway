import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import bittensor as bt

from gateway.core.config import settings
from gateway.subnets.base import AdapterConfig, BaseAdapter


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


class SN1TextAdapter(BaseAdapter):
    """Thin adapter: OpenAI chat format <-> TextGenSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> TextGenSynapse:
        messages = request_data["messages"]
        return TextGenSynapse(
            roles=[m["role"] for m in messages],
            messages=[m["content"] for m in messages],
        )

    def from_response(
        self, synapse: TextGenSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
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

    # Dangerous HTML tags that could execute code or load external content
    _DANGEROUS_TAGS_RE = re.compile(
        r"<\s*/?\s*(?:script|iframe|object|embed|form|input|button|textarea"
        r"|select|style|link|meta|base|applet|svg)\b[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    # Content between script/style tags (strip payload, not just the tags)
    _DANGEROUS_CONTENT_RE = re.compile(
        r"<\s*(?:script|style)\b[^>]*>.*?<\s*/\s*(?:script|style)\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    # Event handler attributes on any tag (onerror, onload, onclick, etc.)
    _EVENT_HANDLER_RE = re.compile(
        r"<([^>]*?\s)on\w+\s*=[^>]*>",
        re.IGNORECASE,
    )
    # javascript: protocol in attributes
    _JS_PROTOCOL_RE = re.compile(
        r"<[^>]*\s(?:href|src|action)\s*=\s*[\"']?\s*javascript\s*:[^>]*>",
        re.IGNORECASE,
    )

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        content = response_data["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        # Strip script/style tags WITH their content (prevent payload leaking as text)
        content = self._DANGEROUS_CONTENT_RE.sub("", content)
        # Strip remaining dangerous tags (unpaired or other dangerous elements)
        content = self._DANGEROUS_TAGS_RE.sub("", content)
        # Strip tags with event handler attributes (e.g., <img onerror="...">)
        content = self._EVENT_HANDLER_RE.sub("", content)
        # Strip tags with javascript: protocol (e.g., <a href="javascript:...">)
        content = self._JS_PROTOCOL_RE.sub("", content)
        content = content.replace("\x00", "")
        response_data["choices"][0]["message"]["content"] = content
        return response_data

    def to_streaming_synapse(
        self, request_data: dict[str, Any]
    ) -> TextGenStreamingSynapse:
        messages = request_data["messages"]
        return TextGenStreamingSynapse(
            roles=[m["role"] for m in messages],
            messages=[m["content"] for m in messages],
        )

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

    def sanitize_text(self, text: str) -> str:
        """Sanitize a single text chunk (reuses dangerous-tag regexes)."""
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        text = self._DANGEROUS_CONTENT_RE.sub("", text)
        text = self._DANGEROUS_TAGS_RE.sub("", text)
        text = self._EVENT_HANDLER_RE.sub("", text)
        text = self._JS_PROTOCOL_RE.sub("", text)
        return text.replace("\x00", "")

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn1_netuid,
            subnet_name="sn1",
            timeout_seconds=settings.dendrite_timeout_seconds,
        )
