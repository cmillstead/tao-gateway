"""Admin endpoint response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SubnetMetrics(BaseModel):
    subnet_name: str
    netuid: int
    request_count: int
    success_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int


class MetricsResponse(BaseModel):
    time_range: str
    subnets: list[SubnetMetrics]
    total_requests: int
    total_errors: int
    overall_error_rate: float


class SubnetMetagraphStatus(BaseModel):
    netuid: int
    subnet_name: str
    last_sync_time: str | None
    staleness_seconds: float
    is_stale: bool
    sync_status: Literal["healthy", "degraded", "never_synced"]
    last_sync_error: str | None
    consecutive_failures: int
    active_miners: int


class MetagraphResponse(BaseModel):
    subnets: list[SubnetMetagraphStatus]


class DeveloperSummary(BaseModel):
    org_id: str
    email: str
    signup_date: str
    last_active: str | None
    total_requests: int
    requests_by_subnet: dict[str, int]


class DeveloperMetrics(BaseModel):
    total_developers: int
    new_signups_today: int
    new_signups_this_week: int
    weekly_active_developers: int
    developers: list[DeveloperSummary]


class MinerInfo(BaseModel):
    miner_uid: int
    hotkey_prefix: str
    netuid: int
    subnet_name: str
    incentive_score: float
    gateway_quality_score: float
    total_requests: int
    successful_requests: int
    avg_latency_ms: float
    error_rate: float


class MinerResponse(BaseModel):
    subnets: dict[str, list[MinerInfo]]
