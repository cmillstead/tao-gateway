"""Tests for SN32 AI Content Detection adapter (Story 7-2).

Uses real Postgres and Redis per CLAUDE.md. Only Bittensor SDK is mocked
at conftest level (paid external network).
"""

from typing import Any

import pytest

from gateway.subnets.sn32_detect import SN32DetectionAdapter, TextSynapse


class TestTextSynapse:
    """Test TextSynapse creation and field defaults."""

    def test_default_fields(self) -> None:
        synapse = TextSynapse()
        assert synapse.texts == []
        assert synapse.predictions == []
        assert synapse.version == ""

    def test_with_texts(self) -> None:
        synapse = TextSynapse(texts=["hello", "world"])
        assert synapse.texts == ["hello", "world"]

    def test_required_hash_fields(self) -> None:
        synapse = TextSynapse()
        assert synapse.required_hash_fields == ["texts"]


class TestSN32DetectionAdapterToSynapse:
    """Test to_synapse() conversion."""

    def setup_method(self) -> None:
        self.adapter = SN32DetectionAdapter()

    def test_single_text(self) -> None:
        synapse = self.adapter.to_synapse({"input": ["test text"]})
        assert isinstance(synapse, TextSynapse)
        assert synapse.texts == ["test text"]

    def test_multiple_texts(self) -> None:
        texts = ["first", "second", "third"]
        synapse = self.adapter.to_synapse({"input": texts})
        assert synapse.texts == texts


class TestSN32DetectionAdapterFromResponse:
    """Test from_response() conversion and validation."""

    def setup_method(self) -> None:
        self.adapter = SN32DetectionAdapter()

    def _make_synapse(self, predictions: list[list[float]]) -> TextSynapse:
        synapse = TextSynapse()
        synapse.predictions = predictions
        return synapse

    def test_single_text_ai_detected(self) -> None:
        synapse = self._make_synapse([[0.1, 0.9]])
        result = self.adapter.from_response(synapse, {"input": ["text"], "model": "tao-sn32"})

        assert result["model"] == "tao-sn32"
        assert result["id"].startswith("mod-")
        assert len(result["results"]) == 1
        assert result["results"][0]["flagged"] is True
        assert result["results"][0]["categories"]["ai_generated"] is True
        assert result["results"][0]["category_scores"]["ai_generated"] == pytest.approx(0.9)

    def test_single_text_human_detected(self) -> None:
        synapse = self._make_synapse([[0.8, 0.2]])
        result = self.adapter.from_response(synapse, {"input": ["text"], "model": "tao-sn32"})

        assert result["results"][0]["flagged"] is False
        assert result["results"][0]["category_scores"]["ai_generated"] == pytest.approx(0.2)

    def test_multiple_texts(self) -> None:
        synapse = self._make_synapse([[0.1, 0.9], [0.8, 0.2], [0.5, 0.5]])
        result = self.adapter.from_response(
            synapse, {"input": ["a", "b", "c"], "model": "tao-sn32"}
        )

        assert len(result["results"]) == 3
        assert result["results"][0]["flagged"] is True
        assert result["results"][1]["flagged"] is False
        assert result["results"][2]["flagged"] is False  # 0.5 is NOT > 0.5

    def test_dimension_mismatch_raises(self) -> None:
        from gateway.core.exceptions import MinerInvalidResponseError

        synapse = self._make_synapse([[0.1, 0.9]])
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.from_response(synapse, {"input": ["a", "b"], "model": "tao-sn32"})

    def test_empty_predictions_raises(self) -> None:
        from gateway.core.exceptions import MinerInvalidResponseError

        synapse = self._make_synapse([])
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.from_response(synapse, {"input": ["a"], "model": "tao-sn32"})

    def test_empty_prediction_array_raises(self) -> None:
        from gateway.core.exceptions import MinerInvalidResponseError

        synapse = self._make_synapse([[]])
        with pytest.raises(MinerInvalidResponseError):
            self.adapter.from_response(synapse, {"input": ["a"], "model": "tao-sn32"})

    def test_score_clamping_high(self) -> None:
        synapse = self._make_synapse([[0.0, 1.5]])
        result = self.adapter.from_response(synapse, {"input": ["text"], "model": "tao-sn32"})
        assert result["results"][0]["category_scores"]["ai_generated"] == 1.0

    def test_score_clamping_low(self) -> None:
        synapse = self._make_synapse([[-0.5, -0.3]])
        result = self.adapter.from_response(synapse, {"input": ["text"], "model": "tao-sn32"})
        assert result["results"][0]["category_scores"]["ai_generated"] == 0.0

    def test_single_element_prediction(self) -> None:
        """When prediction has only one element, use it as AI probability."""
        synapse = self._make_synapse([[0.85]])
        result = self.adapter.from_response(synapse, {"input": ["text"], "model": "tao-sn32"})
        assert result["results"][0]["flagged"] is True
        assert result["results"][0]["category_scores"]["ai_generated"] == pytest.approx(0.85)


class TestSN32DetectionAdapterSanitize:
    """Test sanitize_output() score clamping and flagged verification."""

    def setup_method(self) -> None:
        self.adapter = SN32DetectionAdapter()

    def test_clamps_out_of_range_scores(self) -> None:
        data: dict[str, Any] = {
            "id": "mod-test",
            "model": "tao-sn32",
            "results": [
                {
                    "flagged": True,
                    "categories": {"ai_generated": True},
                    "category_scores": {"ai_generated": 1.5},
                }
            ],
        }
        result = self.adapter.sanitize_output(data)
        assert result["results"][0]["category_scores"]["ai_generated"] == 1.0

    def test_corrects_flagged_mismatch(self) -> None:
        data: dict[str, Any] = {
            "id": "mod-test",
            "model": "tao-sn32",
            "results": [
                {
                    "flagged": True,  # Wrong — score is 0.3
                    "categories": {"ai_generated": True},
                    "category_scores": {"ai_generated": 0.3},
                }
            ],
        }
        result = self.adapter.sanitize_output(data)
        assert result["results"][0]["flagged"] is False


class TestSN32DetectionAdapterConfig:
    """Test get_config(), get_capability(), get_parameters()."""

    def setup_method(self) -> None:
        self.adapter = SN32DetectionAdapter()

    def test_config(self) -> None:
        config = self.adapter.get_config()
        assert config.netuid == 32
        assert config.subnet_name == "sn32-detect"
        assert config.timeout_seconds == 30

    def test_capability(self) -> None:
        assert self.adapter.get_capability() == "AI Content Detection"

    def test_parameters(self) -> None:
        params = self.adapter.get_parameters()
        assert "input" in params
        assert "model" in params
