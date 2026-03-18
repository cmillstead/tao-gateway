"""SN32 Its-AI text detection adapter — AI content detection."""

import uuid
from typing import Any

import bittensor as bt

from gateway.core.config import settings
from gateway.core.exceptions import MinerInvalidResponseError
from gateway.subnets.base import AdapterConfig, BaseAdapter


class TextSynapse(bt.Synapse):  # type: ignore[misc]
    """SN32 Its-AI text detection synapse.

    Source: GitHub It-s-AI/llm-detection/detection/protocol.py
    """

    texts: list[str] = []
    predictions: list[list[float]] = []
    version: str = ""
    required_hash_fields: list[str] = ["texts"]


class SN32DetectionAdapter(BaseAdapter):
    """Thin adapter: detection request <-> TextSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> TextSynapse:
        return TextSynapse(texts=request_data["input"])

    def from_response(
        self, synapse: TextSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        input_texts = request_data["input"]
        predictions = synapse.predictions

        if not predictions or len(predictions) != len(input_texts):
            raise MinerInvalidResponseError(
                miner_uid="unknown",
                subnet="sn32-detect",
            )

        results = []
        for pred in predictions:
            if not pred:
                raise MinerInvalidResponseError(
                    miner_uid="unknown",
                    subnet="sn32-detect",
                )
            # Use last element as AI probability (defensive)
            ai_prob = max(0.0, min(1.0, pred[-1]))
            flagged = ai_prob > 0.5
            results.append({
                "flagged": flagged,
                "categories": {"ai_generated": flagged},
                "category_scores": {"ai_generated": ai_prob},
            })

        model = request_data.get("model", "tao-sn32")
        return {
            "id": f"mod-{uuid.uuid4().hex[:24]}",
            "model": model,
            "results": results,
        }

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        # Output is numeric — clamp scores and verify flagged matches
        for result in response_data.get("results", []):
            scores = result.get("category_scores", {})
            for key, score in scores.items():
                scores[key] = max(0.0, min(1.0, score))
            ai_score = scores.get("ai_generated", 0.0)
            flagged = ai_score > 0.5
            result["flagged"] = flagged
            result["categories"] = {"ai_generated": flagged}
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn32_netuid,
            subnet_name="sn32-detect",
            timeout_seconds=settings.sn32_timeout_seconds,
        )

    def get_capability(self) -> str:
        return "AI Content Detection"

    def get_parameters(self) -> dict[str, str]:
        return {
            "input": "Array of text strings (1-20, max 10K chars each)",
            "model": "tao-sn32",
        }
