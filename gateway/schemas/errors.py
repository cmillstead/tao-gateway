from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    message: str
    code: int
    subnet: str | None = None
    retry_after: int | None = None
    miner_uid: str | None = None
    reason: str | None = None
    errors: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
