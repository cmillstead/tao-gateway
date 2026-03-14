from typing import Literal

from pydantic import BaseModel


class SubnetHealthStatus(BaseModel):
    netuid: int
    subnet_name: str = ""
    status: Literal["healthy", "degraded", "unavailable"] = "unavailable"
    neuron_count: int | None = None
    last_sync: str | None = None
    is_stale: bool = True
    sync_error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    version: str
    uptime_seconds: float
    database: Literal["healthy", "unhealthy"]
    redis: Literal["healthy", "unhealthy"]
    subnets: dict[str, SubnetHealthStatus] = {}
