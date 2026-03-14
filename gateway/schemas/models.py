from typing import Any, Literal

from pydantic import BaseModel


class SubnetModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "tao-gateway"
    subnet_id: int
    capability: str
    status: Literal["available", "unavailable"]
    parameters: dict[str, Any] = {}


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[SubnetModelInfo]
