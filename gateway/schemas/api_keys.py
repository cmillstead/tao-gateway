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
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyListItem]
    total: int


class ApiKeyRevokeResponse(BaseModel):
    message: str


class ApiKeyRotateResponse(BaseModel):
    new_key: ApiKeyCreateResponse
    revoked_key_id: str
