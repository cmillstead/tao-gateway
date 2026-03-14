from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SubnetRateLimits(BaseModel):
    minute: int
    day: int
    month: int


class SubnetOverview(BaseModel):
    name: str
    netuid: int
    status: Literal["healthy", "degraded", "unavailable"]
    rate_limits: SubnetRateLimits


class OverviewResponse(BaseModel):
    email: str
    tier: str
    created_at: datetime
    api_key_count: int
    first_api_key_prefix: str | None
    subnets: list[SubnetOverview]
