from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    environment: Literal["live", "test"] = "live"


class ApiKeyCreateResponse(BaseModel):
    id: str
    key: str
    prefix: str
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: str
    prefix: str
    is_active: bool
    created_at: datetime


class ApiKeyRevokeResponse(BaseModel):
    message: str
