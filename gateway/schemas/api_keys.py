from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    environment: Literal["live", "test"] = "live"
    name: str | None = Field(default=None, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: str
    key: str
    prefix: str
    name: str | None
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: str
    prefix: str
    name: str | None
    is_active: bool
    debug_mode: bool
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyListItem]
    total: int


class ApiKeyRevokeResponse(BaseModel):
    message: str


class ApiKeyRotateResponse(BaseModel):
    new_key: ApiKeyCreateResponse
    revoked_key_id: str


class ApiKeyUpdateRequest(BaseModel):
    debug_mode: bool | None = None


class DebugLogEntry(BaseModel):
    id: str
    usage_record_id: str
    request_body: str | None
    response_body: str | None
    created_at: datetime


class DebugLogListResponse(BaseModel):
    items: list[DebugLogEntry]
    total: int
