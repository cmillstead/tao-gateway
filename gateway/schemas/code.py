from typing import Literal

from pydantic import BaseModel, Field


class CodeCompletionRequest(BaseModel):
    model: str = Field(default="tao-sn62", min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=16000)
    language: str = Field(min_length=1, max_length=32)
    context: str | None = Field(default=None, max_length=32000)


class CodeChoice(BaseModel):
    index: int
    code: str
    language: str
    finish_reason: Literal["stop"] = "stop"


class CodeCompletionResponse(BaseModel):
    id: str
    object: Literal["code.completion"] = "code.completion"
    created: int
    model: str
    choices: list[CodeChoice]
