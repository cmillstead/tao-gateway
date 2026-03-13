import re
import time
import uuid
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

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        content = response_data["choices"][0]["message"]["content"]
        # Strip all HTML tags — SN1 returns plain text, no legitimate HTML
        content = re.sub(r"<[^>]*>", "", content)
        content = content.replace("\x00", "")
        response_data["choices"][0]["message"]["content"] = content
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn1_netuid,
            subnet_name="sn1",
            timeout_seconds=settings.dendrite_timeout_seconds,
        )
