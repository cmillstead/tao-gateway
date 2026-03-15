"""Admin service: cross-org metrics and developer activity queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from gateway.models.daily_usage_summary import DailyUsageSummary
from gateway.models.organization import Organization
from gateway.models.usage_record import UsageRecord
from gateway.schemas.admin import (
    DeveloperMetrics,
    DeveloperSummary,
    MetricsResponse,
    SubnetMetrics,
)


def _time_range_to_dates(time_range: str) -> tuple[datetime, datetime]:
    """Convert time_range string to (start, end) datetime range."""
    now = datetime.now(UTC)
    if time_range == "1h":
        return now - timedelta(hours=1), now
    if time_range == "24h":
        return now - timedelta(hours=24), now
    if time_range == "7d":
        return now - timedelta(days=7), now
    # 30d
    return now - timedelta(days=30), now


async def get_system_metrics(
    db: AsyncSession,
    time_range: str = "24h",
) -> MetricsResponse:
    """Aggregate cross-org usage metrics per subnet for the given time range."""
    now = datetime.now(UTC)
    today = now.date()
    start_dt, _ = _time_range_to_dates(time_range)

    subnet_data: dict[int, dict[str, Any]] = {}

    if time_range == "1h":
        # Live data only from UsageRecord
        stmt = (
            select(
                UsageRecord.netuid,
                UsageRecord.subnet_name,
                func.count().label("request_count"),
                func.count().filter(
                    UsageRecord.status_code >= 200, UsageRecord.status_code < 400
                ).label("success_count"),
                func.count().filter(UsageRecord.status_code >= 400).label("error_count"),
                func.coalesce(func.avg(UsageRecord.latency_ms), 0).label("avg_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.5).within_group(UsageRecord.latency_ms), 0
                ).label("p50_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.95).within_group(UsageRecord.latency_ms), 0
                ).label("p95_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.99).within_group(UsageRecord.latency_ms), 0
                ).label("p99_latency_ms"),
            )
            .where(UsageRecord.created_at >= start_dt)
            .group_by(UsageRecord.netuid, UsageRecord.subnet_name)
        )
        rows = await db.execute(stmt)
        for row in rows:
            subnet_data[row.netuid] = {
                "subnet_name": row.subnet_name,
                "netuid": row.netuid,
                "request_count": row.request_count,
                "success_count": row.success_count,
                "error_count": row.error_count,
                "avg_latency_ms": float(row.avg_latency_ms),
                "p50_latency_ms": int(row.p50_latency_ms),
                "p95_latency_ms": int(row.p95_latency_ms),
                "p99_latency_ms": int(row.p99_latency_ms),
            }
    else:
        # DailyUsageSummary for completed days + UsageRecord for today
        summary_start = start_dt.date()
        summary_end = today - timedelta(days=1)

        if summary_start <= summary_end:
            stmt_summary = (
                select(
                    DailyUsageSummary.netuid,
                    DailyUsageSummary.subnet_name,
                    func.sum(DailyUsageSummary.request_count).label("request_count"),
                    func.sum(DailyUsageSummary.success_count).label("success_count"),
                    func.sum(DailyUsageSummary.error_count).label("error_count"),
                    func.avg(DailyUsageSummary.p50_latency_ms).label("p50_latency_ms"),
                    func.avg(DailyUsageSummary.p95_latency_ms).label("p95_latency_ms"),
                    func.avg(DailyUsageSummary.p99_latency_ms).label("p99_latency_ms"),
                )
                .where(
                    DailyUsageSummary.summary_date >= summary_start,
                    DailyUsageSummary.summary_date <= summary_end,
                )
                .group_by(DailyUsageSummary.netuid, DailyUsageSummary.subnet_name)
            )
            rows = await db.execute(stmt_summary)
            for row in rows:
                req_count = int(row.request_count)
                subnet_data[row.netuid] = {
                    "subnet_name": row.subnet_name,
                    "netuid": row.netuid,
                    "request_count": req_count,
                    "success_count": int(row.success_count),
                    "error_count": int(row.error_count),
                    "avg_latency_ms": 0.0,
                    "p50_latency_ms": int(row.p50_latency_ms or 0),
                    "p95_latency_ms": int(row.p95_latency_ms or 0),
                    "p99_latency_ms": int(row.p99_latency_ms or 0),
                }

        # Add today's live data
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
                func.coalesce(func.avg(UsageRecord.latency_ms), 0).label("avg_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.5).within_group(UsageRecord.latency_ms), 0
                ).label("p50_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.95).within_group(UsageRecord.latency_ms), 0
                ).label("p95_latency_ms"),
                func.coalesce(
                    func.percentile_cont(0.99).within_group(UsageRecord.latency_ms), 0
                ).label("p99_latency_ms"),
            )
            .where(
                UsageRecord.created_at >= today_start,
                UsageRecord.created_at < today_end,
            )
            .group_by(UsageRecord.netuid, UsageRecord.subnet_name)
        )
        rows = await db.execute(stmt_today)
        for row in rows:
            if row.netuid in subnet_data:
                d = subnet_data[row.netuid]
                d["request_count"] += row.request_count
                d["success_count"] += row.success_count
                d["error_count"] += row.error_count
                # Use today's percentiles as approximation when combined
                d["p50_latency_ms"] = int(row.p50_latency_ms)
                d["p95_latency_ms"] = int(row.p95_latency_ms)
                d["p99_latency_ms"] = int(row.p99_latency_ms)
            else:
                subnet_data[row.netuid] = {
                    "subnet_name": row.subnet_name,
                    "netuid": row.netuid,
                    "request_count": row.request_count,
                    "success_count": row.success_count,
                    "error_count": row.error_count,
                    "avg_latency_ms": float(row.avg_latency_ms),
                    "p50_latency_ms": int(row.p50_latency_ms),
                    "p95_latency_ms": int(row.p95_latency_ms),
                    "p99_latency_ms": int(row.p99_latency_ms),
                }

    # Build response
    subnets: list[SubnetMetrics] = []
    total_requests = 0
    total_errors = 0
    for d in subnet_data.values():
        req = d["request_count"]
        err = d["error_count"]
        total_requests += req
        total_errors += err
        error_rate = err / req if req > 0 else 0.0
        # Compute avg_latency_ms from p50 if not set from live data
        avg_lat = d.get("avg_latency_ms", 0.0)
        if avg_lat == 0.0 and d["p50_latency_ms"] > 0:
            avg_lat = float(d["p50_latency_ms"])
        subnets.append(
            SubnetMetrics(
                subnet_name=d["subnet_name"],
                netuid=d["netuid"],
                request_count=req,
                success_count=d["success_count"],
                error_count=err,
                error_rate=round(error_rate, 4),
                avg_latency_ms=round(avg_lat, 1),
                p50_latency_ms=d["p50_latency_ms"],
                p95_latency_ms=d["p95_latency_ms"],
                p99_latency_ms=d["p99_latency_ms"],
            )
        )

    overall_error_rate = total_errors / total_requests if total_requests > 0 else 0.0

    return MetricsResponse(
        time_range=time_range,
        subnets=sorted(subnets, key=lambda s: s.netuid),
        total_requests=total_requests,
        total_errors=total_errors,
        overall_error_rate=round(overall_error_rate, 4),
    )


async def get_developer_metrics(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> DeveloperMetrics:
    """Query cross-org developer signup and activity metrics."""
    now = datetime.now(UTC)
    today = now.date()
    today_start = datetime(today.year, today.month, today.day, tzinfo=UTC)
    week_ago = today_start - timedelta(days=7)

    # Total developers
    total = await db.scalar(select(func.count()).select_from(Organization))
    total_developers = total or 0

    # New signups today
    new_today = await db.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.created_at >= today_start)
    )
    new_signups_today = new_today or 0

    # New signups this week
    new_week = await db.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.created_at >= week_ago)
    )
    new_signups_this_week = new_week or 0

    # Weekly active developers (orgs with any UsageRecord in last 7 days)
    active_count = await db.scalar(
        select(func.count(func.distinct(UsageRecord.org_id)))
        .where(UsageRecord.created_at >= week_ago)
    )
    weekly_active_developers = active_count or 0

    # Per-developer summary — paginated to avoid unbounded response (SEC-009)
    orgs = (await db.execute(
        select(Organization.id, Organization.email, Organization.created_at)
        .order_by(Organization.created_at.desc())
        .limit(limit)
        .offset(offset)
    )).all()

    # Batch: last active + total requests per org
    usage_agg_rows = (await db.execute(
        select(
            UsageRecord.org_id,
            func.max(UsageRecord.created_at).label("last_active"),
            func.count().label("total_requests"),
        )
        .group_by(UsageRecord.org_id)
    )).all()
    usage_agg = {
        row.org_id: (row.last_active, row.total_requests)
        for row in usage_agg_rows
    }

    # Batch: per-subnet request counts per org
    subnet_agg_rows = (await db.execute(
        select(
            UsageRecord.org_id,
            UsageRecord.subnet_name,
            func.count().label("req_count"),
        )
        .group_by(UsageRecord.org_id, UsageRecord.subnet_name)
    )).all()
    subnet_agg: dict[Any, dict[str, int]] = {}
    for row in subnet_agg_rows:
        subnet_agg.setdefault(row.org_id, {})[row.subnet_name] = row.req_count

    developers: list[DeveloperSummary] = []
    for org in orgs:
        last_active_dt, total_req = usage_agg.get(org.id, (None, 0))
        last_active = last_active_dt.isoformat() if last_active_dt else None
        requests_by_subnet = subnet_agg.get(org.id, {})

        developers.append(
            DeveloperSummary(
                org_id=str(org.id),
                email=org.email,
                signup_date=org.created_at.isoformat(),
                last_active=last_active,
                total_requests=total_req or 0,
                requests_by_subnet=requests_by_subnet,
            )
        )

    return DeveloperMetrics(
        total_developers=total_developers,
        new_signups_today=new_signups_today,
        new_signups_this_week=new_signups_this_week,
        weekly_active_developers=weekly_active_developers,
        developers=developers,
    )
