"""Tests for detection request/response schemas (Story 7-2)."""

import pytest
from pydantic import ValidationError

from gateway.schemas.detection import DetectionRequest, DetectionResponse, DetectionResult


class TestDetectionRequest:
    """Test DetectionRequest validation."""

    def test_valid_single_text(self) -> None:
        req = DetectionRequest(input=["Hello world"])
        assert req.input == ["Hello world"]
        assert req.model == "tao-sn32"

    def test_valid_multiple_texts(self) -> None:
        req = DetectionRequest(input=["text1", "text2", "text3"])
        assert len(req.input) == 3

    def test_custom_model(self) -> None:
        req = DetectionRequest(input=["text"], model="custom-model")
        assert req.model == "custom-model"

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            DetectionRequest(input=[])

    def test_rejects_too_many_texts(self) -> None:
        with pytest.raises(ValidationError, match="too_long"):
            DetectionRequest(input=["text"] * 21)

    def test_accepts_max_texts(self) -> None:
        req = DetectionRequest(input=["text"] * 20)
        assert len(req.input) == 20

    def test_rejects_text_too_long(self) -> None:
        with pytest.raises(ValidationError, match="10,000 characters"):
            DetectionRequest(input=["x" * 10_001])

    def test_accepts_max_length_text(self) -> None:
        req = DetectionRequest(input=["x" * 10_000])
        assert len(req.input[0]) == 10_000

    def test_rejects_empty_text_string(self) -> None:
        with pytest.raises(ValidationError, match="Empty text"):
            DetectionRequest(input=["valid", "   "])

    def test_rejects_whitespace_only_text(self) -> None:
        with pytest.raises(ValidationError, match="Empty text"):
            DetectionRequest(input=["\t\n  "])

    def test_rejects_empty_model(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            DetectionRequest(input=["text"], model="")


class TestDetectionResult:
    """Test DetectionResult schema."""

    def test_valid_result(self) -> None:
        result = DetectionResult(
            flagged=True,
            categories={"ai_generated": True},
            category_scores={"ai_generated": 0.92},
        )
        assert result.flagged is True
        assert result.category_scores["ai_generated"] == 0.92


class TestDetectionResponse:
    """Test DetectionResponse schema."""

    def test_valid_response(self) -> None:
        resp = DetectionResponse(
            id="mod-abc123",
            model="tao-sn32",
            results=[
                DetectionResult(
                    flagged=True,
                    categories={"ai_generated": True},
                    category_scores={"ai_generated": 0.92},
                )
            ],
        )
        assert resp.id == "mod-abc123"
        assert len(resp.results) == 1

    def test_empty_results(self) -> None:
        resp = DetectionResponse(id="mod-abc", model="tao-sn32", results=[])
        assert resp.results == []
