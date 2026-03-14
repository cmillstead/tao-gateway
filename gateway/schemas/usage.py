from __future__ import annotations

from datetime import date  # noqa: TC003

from pydantic import BaseModel, Field


class UsageSummary(BaseModel):
    """Usage data for a single time period (day or month)."""

    period: str = Field(description="Date string: YYYY-MM-DD for daily, YYYY-MM for monthly")
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    p50_latency_ms: int = 0
    p95_latency_ms: int = 0
    p99_latency_ms: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0


class SubnetUsage(BaseModel):
    """Usage data for a single subnet."""

    subnet_name: str
    netuid: int
    summaries: list[UsageSummary] = Field(default_factory=list)


class UsageResponse(BaseModel):
    """Response for GET /v1/usage."""

    start_date: date
    end_date: date
    granularity: str
    subnets: list[SubnetUsage] = Field(default_factory=list)


class SubnetQuota(BaseModel):
    """Quota status for a single subnet."""

    subnet_name: str
    netuid: int
    monthly_limit: int
    monthly_used: int
    monthly_remaining: int


class SubnetUsageWithQuota(SubnetUsage):
    """Subnet usage with quota information for dashboard."""

    quota: SubnetQuota | None = None


class DashboardUsageResponse(BaseModel):
    """Response for GET /dashboard/usage."""

    start_date: date
    end_date: date
    granularity: str
    subnets: list[SubnetUsageWithQuota] = Field(default_factory=list)


