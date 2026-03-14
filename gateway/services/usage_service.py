"""Usage data queries and quota calculation."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from gateway.middleware.rate_limit import get_subnet_rate_limits
from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.usage_record import UsageRecord
from gateway.schemas.usage import (
    SubnetQuota,
    SubnetUsageWithQuota,
    UsageSummary,
)

# Subnets tracked for quota display
_TRACKED_SUBNETS: dict[int, str] = {
    1: "sn1",
    19: "sn19",
    62: "sn62",
}


async def get_usage_summaries(
    db: AsyncSession,
    org_id: uuid.UUID,
    start_date: date,
    end_date: date,
    granularity: str = "daily",
    subnet_filter: str | None = None,
) -> list[SubnetUsageWithQuota]:
    """Query usage summaries for an org within a date range.

    Uses daily_usage_summaries for completed days and usage_records for today.
    """
    today = datetime.now(UTC).date()
    results_by_subnet: dict[int, SubnetUsageWithQuota] = {}

    # Query daily_usage_summaries for completed days
    summary_end = min(end_date, today - timedelta(days=1))
    if start_date <= summary_end:
        stmt = (
            select(
                DailyUsageSummary.netuid,
                DailyUsageSummary.subnet_name,
                DailyUsageSummary.summary_date,
                func.sum(DailyUsageSummary.request_count).label("request_count"),
                func.sum(DailyUsageSummary.success_count).label("success_count"),
                func.sum(DailyUsageSummary.error_count).label("error_count"),
                func.avg(DailyUsageSummary.p50_latency_ms).label("p50_latency_ms"),
                func.avg(DailyUsageSummary.p95_latency_ms).label("p95_latency_ms"),
                func.avg(DailyUsageSummary.p99_latency_ms).label("p99_latency_ms"),
                func.sum(DailyUsageSummary.total_prompt_tokens).label("total_prompt_tokens"),
                func.sum(DailyUsageSummary.total_completion_tokens).label("total_completion_tokens"),
            )
            .where(
                DailyUsageSummary.org_id == org_id,
                DailyUsageSummary.summary_date >= start_date,
                DailyUsageSummary.summary_date <= summary_end,
            )
            .group_by(
                DailyUsageSummary.netuid,
                DailyUsageSummary.subnet_name,
                DailyUsageSummary.summary_date,
            )
            .order_by(DailyUsageSummary.summary_date)
        )
        if subnet_filter:
            stmt = stmt.where(DailyUsageSummary.subnet_name == subnet_filter)

        rows = await db.execute(stmt)
        for row in rows:
            netuid = row.netuid
            if netuid not in results_by_subnet:
                results_by_subnet[netuid] = SubnetUsageWithQuota(
                    subnet_name=row.subnet_name,
                    netuid=netuid,
                )
            results_by_subnet[netuid].summaries.append(
                UsageSummary(
                    period=row.summary_date.isoformat(),
                    request_count=row.request_count,
                    success_count=row.success_count,
                    error_count=row.error_count,
                    p50_latency_ms=int(row.p50_latency_ms or 0),
                    p95_latency_ms=int(row.p95_latency_ms or 0),
                    p99_latency_ms=int(row.p99_latency_ms or 0),
                    total_prompt_tokens=row.total_prompt_tokens or 0,
                    total_completion_tokens=row.total_completion_tokens or 0,
                )
            )

    # Query live usage_records for today (if today is in range)
    if start_date <= today <= end_date:
        today_start = datetime(today.year, today.month, today.day, tzinfo=UTC)
        today_end = today_start + timedelta(days=1)

        stmt_today = (
            select(
                UsageRecord.netuid,
                UsageRecord.subnet_name,
                func.count().label("request_count"),
                func.count().filter(
                    UsageRecord.status_code >= 200, UsageRecord.status_code < 400
                ).label("success_count"),
                func.count().filter(UsageRecord.status_code >= 400).label("error_count"),
                func.coalesce(
                    func.percentile_cont(0.5).within_group(UsageRecord.latency_ms), 0
                ).label("p50_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.95).within_group(UsageRecord.latency_ms), 0
                ).label("p95_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.99).within_group(UsageRecord.latency_ms), 0
                ).label("p99_latency_ms"),
                func.sum(UsageRecord.prompt_tokens).label("total_prompt_tokens"),
                func.sum(UsageRecord.completion_tokens).label("total_completion_tokens"),
            )
            .where(
                UsageRecord.org_id == org_id,
                UsageRecord.created_at >= today_start,
                UsageRecord.created_at < today_end,
            )
            .group_by(UsageRecord.netuid, UsageRecord.subnet_name)
        )
        if subnet_filter:
            stmt_today = stmt_today.where(UsageRecord.subnet_name == subnet_filter)

        rows = await db.execute(stmt_today)
        for row in rows:
            netuid = row.netuid
            if netuid not in results_by_subnet:
                results_by_subnet[netuid] = SubnetUsageWithQuota(
                    subnet_name=row.subnet_name,
                    netuid=netuid,
                )
            results_by_subnet[netuid].summaries.append(
                UsageSummary(
                    period=today.isoformat(),
                    request_count=row.request_count,
                    success_count=row.success_count,
                    error_count=row.error_count,
                    p50_latency_ms=int(row.p50_latency_ms or 0),
                    p95_latency_ms=int(row.p95_latency_ms or 0),
                    p99_latency_ms=int(row.p99_latency_ms or 0),
                    total_prompt_tokens=row.total_prompt_tokens or 0,
                    total_completion_tokens=row.total_completion_tokens or 0,
                )
            )

    # If monthly granularity, aggregate daily summaries into months
    if granularity == "monthly":
        for subnet_usage in results_by_subnet.values():
            subnet_usage.summaries = _aggregate_to_monthly(subnet_usage.summaries)

    return sorted(results_by_subnet.values(), key=lambda s: s.netuid)


def _aggregate_to_monthly(summaries: list[UsageSummary]) -> list[UsageSummary]:
    """Aggregate daily summaries into monthly buckets."""
    monthly: dict[str, UsageSummary] = {}
    for s in summaries:
        month_key = s.period[:7]  # YYYY-MM
        if month_key not in monthly:
            monthly[month_key] = UsageSummary(period=month_key)
        m = monthly[month_key]
        m.request_count += s.request_count
        m.success_count += s.success_count
        m.error_count += s.error_count
        m.total_prompt_tokens += s.total_prompt_tokens
        m.total_completion_tokens += s.total_completion_tokens
        # For latency, keep the max of daily values as approximation
        m.p50_latency_ms = max(m.p50_latency_ms, s.p50_latency_ms)
        m.p95_latency_ms = max(m.p95_latency_ms, s.p95_latency_ms)
        m.p99_latency_ms = max(m.p99_latency_ms, s.p99_latency_ms)
    return sorted(monthly.values(), key=lambda s: s.period)


async def get_quota_status(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[SubnetQuota]:
    """Get current month's quota status per subnet for an org."""
    today = datetime.now(UTC).date()
    month_start = today.replace(day=1)

    # Count this month's requests per subnet from daily summaries + today's records
    # Daily summaries for completed days this month
    summary_counts_stmt = (
        select(
            DailyUsageSummary.netuid,
            func.sum(DailyUsageSummary.request_count).label("total"),
        )
        .where(
            DailyUsageSummary.org_id == org_id,
            DailyUsageSummary.summary_date >= month_start,
        )
        .group_by(DailyUsageSummary.netuid)
    )
    summary_rows = await db.execute(summary_counts_stmt)
    counts: dict[int, int] = {
        row.netuid: int(row.total) for row in summary_rows
    }

    # Today's live records
    today_start = datetime(today.year, today.month, today.day, tzinfo=UTC)
    today_end = today_start + timedelta(days=1)
    today_counts_stmt = (
        select(
            UsageRecord.netuid,
            func.count().label("total"),
        )
        .where(
            UsageRecord.org_id == org_id,
            UsageRecord.created_at >= today_start,
            UsageRecord.created_at < today_end,
        )
        .group_by(UsageRecord.netuid)
    )
    today_rows = await db.execute(today_counts_stmt)
    for row in today_rows:
        counts[row.netuid] = counts.get(row.netuid, 0) + int(row.total)

    quotas: list[SubnetQuota] = []
    for netuid, subnet_name in _TRACKED_SUBNETS.items():
        limits = get_subnet_rate_limits(netuid)
        monthly_limit = limits.get("month", 0)
        monthly_used = counts.get(netuid, 0)
        quotas.append(
            SubnetQuota(
                subnet_name=subnet_name,
                netuid=netuid,
                monthly_limit=monthly_limit,
                monthly_used=monthly_used,
                monthly_remaining=max(0, monthly_limit - monthly_used),
            )
        )

    return quotas
