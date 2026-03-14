import time
import uuid
from typing import Any

import bittensor as bt

from gateway.core.config import settings
from gateway.core.exceptions import MinerInvalidResponseError
from gateway.subnets.base import AdapterConfig, BaseAdapter


def _generate_code_completion_id() -> str:
    return f"codecmpl-{uuid.uuid4().hex[:24]}"


class CodeSynapse(bt.Synapse):  # type: ignore[misc]
    """SN62 code generation synapse."""

    prompt: str = ""
    language: str = ""
    context: str = ""
    # Response fields (populated by miner)
    code: str = ""
    completion_language: str = ""
    required_hash_fields: list[str] = ["prompt"]


class SN62CodeAdapter(BaseAdapter):
    """Thin adapter: code generation request <-> CodeSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> CodeSynapse:
        return CodeSynapse(
            prompt=request_data["prompt"],
            language=request_data.get("language", ""),
            context=request_data.get("context") or "",
        )

    def from_response(
        self, synapse: CodeSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        code = synapse.code
        if not code:
            raise MinerInvalidResponseError(
                miner_uid="unknown", subnet="sn62"
            )

        return {
            "id": _generate_code_completion_id(),
            "object": "code.completion",
            "created": int(time.time()),
            "model": request_data.get("model", "tao-sn62"),
            "choices": [
                {
                    "index": 0,
                    "code": code,
                    "language": synapse.completion_language or request_data.get("language", ""),
                    "finish_reason": "stop",
                }
            ],
        }

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        for choice in response_data.get("choices", []):
            # Do NOT sanitize the code field — nh3.clean() mangles angle
            # brackets (<, >, <=, >=) and strips generics (vector<int>).
            # Code is returned as JSON, not HTML; XSS prevention is the
            # consumer's responsibility when rendering.
            if choice.get("language") is not None:
                choice["language"] = self.sanitize_text(choice["language"])
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn62_netuid,
            subnet_name="sn62",
            timeout_seconds=settings.sn62_timeout_seconds,
        )
