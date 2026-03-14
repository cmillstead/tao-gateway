import base64
import time
from typing import Any

import bittensor as bt

from gateway.core.config import settings
from gateway.core.exceptions import MinerInvalidResponseError
from gateway.subnets.base import AdapterConfig, BaseAdapter

# PNG magic bytes and JPEG SOI marker for image validation
_PNG_MAGIC = b"\x89PNG"
_JPEG_MAGIC = b"\xff\xd8\xff"


class ImageGenSynapse(bt.Synapse):  # type: ignore[misc]
    """SN19 image generation synapse."""

    prompt: str = ""
    size: str = "1024x1024"
    style: str = "natural"
    # Response fields (populated by miner)
    image_data: str = ""
    revised_prompt: str = ""
    required_hash_fields: list[str] = ["prompt"]


class SN19ImageAdapter(BaseAdapter):
    """Thin adapter: image generation request <-> ImageGenSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> ImageGenSynapse:
        return ImageGenSynapse(
            prompt=request_data["prompt"],
            size=request_data.get("size", "1024x1024"),
            style=request_data.get("style") or "natural",
        )

    def from_response(
        self, synapse: ImageGenSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        image_data_str = synapse.image_data
        if not image_data_str:
            raise MinerInvalidResponseError(
                miner_uid="unknown", subnet="sn19"
            )

        image_entry: dict[str, str | None] = {
            "b64_json": image_data_str,
            "revised_prompt": synapse.revised_prompt or None,
        }

        return {
            "created": int(time.time()),
            "data": [image_entry],
        }

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        for image_entry in response_data.get("data", []):
            # Sanitize revised_prompt (miner text is untrusted)
            if image_entry.get("revised_prompt"):
                image_entry["revised_prompt"] = self.sanitize_text(
                    image_entry["revised_prompt"]
                )

            # Validate base64 image data has valid image header
            b64_data = image_entry.get("b64_json")
            if b64_data:
                self._validate_image_header(b64_data)

        return response_data

    @staticmethod
    def _validate_image_header(b64_data: str) -> None:
        """Validate that base64 data starts with PNG or JPEG magic bytes."""
        try:
            # Grab first 16 base64 chars (decodes to 12 bytes) — enough for
            # both PNG (4-byte magic) and JPEG (3-byte SOI) headers.
            # Pad to multiple of 4 to avoid padding errors on the slice.
            snippet = b64_data[:16]
            pad = (4 - len(snippet) % 4) % 4
            header_bytes = base64.b64decode(snippet + "=" * pad)
        except Exception as exc:
            raise MinerInvalidResponseError(
                miner_uid="unknown",
                subnet="sn19",
            ) from exc

        if not (
            header_bytes.startswith(_PNG_MAGIC)
            or header_bytes.startswith(_JPEG_MAGIC)
        ):
            raise MinerInvalidResponseError(
                miner_uid="unknown",
                subnet="sn19",
            )

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn19_netuid,
            subnet_name="sn19",
            timeout_seconds=settings.sn19_timeout_seconds,
        )
