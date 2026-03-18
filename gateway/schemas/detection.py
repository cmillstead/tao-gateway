"""Pydantic schemas for AI content detection (SN32)."""

from pydantic import BaseModel, Field, field_validator


class DetectionRequest(BaseModel):
    model: str = Field(default="tao-sn32", min_length=1, max_length=64)
    input: list[str] = Field(..., min_length=1, max_length=20)

    @field_validator("input")
    @classmethod
    def validate_texts(cls, v: list[str]) -> list[str]:
        for text in v:
            if len(text) > 10_000:
                raise ValueError("Text exceeds maximum length of 10,000 characters")
            if not text.strip():
                raise ValueError("Empty text in input array")
        return v


class DetectionResult(BaseModel):
    flagged: bool
    categories: dict[str, bool]
    category_scores: dict[str, float]


class DetectionResponse(BaseModel):
    id: str
    model: str
    results: list[DetectionResult]
