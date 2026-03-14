import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.exceptions import AuthenticationError
from gateway.middleware.auth import get_current_org_id
from gateway.middleware.rate_limit import get_subnet_rate_limits
from gateway.models.api_key import ApiKey
from gateway.models.organization import Organization
from gateway.schemas.dashboard import (
    OverviewResponse,
    SubnetOverview,
    SubnetRateLimits,
)
from gateway.schemas.usage import DashboardUsageResponse
from gateway.services.usage_service import get_quota_status, get_usage_summaries

if TYPE_CHECKING:
    from gateway.routing.metagraph_sync import MetagraphManager
    from gateway.subnets.registry import AdapterRegistry

logger = structlog.get_logger()
router = APIRouter()

# Human-readable capability names for each subnet netuid
_SUBNET_NAMES: dict[int, str] = {
    1: "Text Generation",
    19: "Image Generation",
    62: "Code Generation",
}


def _get_subnet_status(request: Request, netuid: int) -> str:
    """Derive subnet health status from metagraph state."""
    mgr: MetagraphManager | None = getattr(
        request.app.state, "metagraph_manager", None
    )
    if mgr is None:
        return "unavailable"

    state = mgr.get_state(netuid)
    if state is None or state.metagraph is None:
        return "unavailable"
    if state.is_stale:
        return "degraded"
    return "healthy"


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    request: Request,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    """Return account overview: tier, key count, subnet health, rate limits."""
    # Fetch org details
    org = await db.get(Organization, org_id)
    if org is None:
        raise AuthenticationError("Organization not found")

    # Count active API keys
    key_count_result = await db.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.org_id == org_id, ApiKey.is_active.is_(True))
    )
    api_key_count = key_count_result or 0

    # Get first active key prefix for quickstart snippets
    first_key = await db.scalar(
        select(ApiKey.prefix)
        .where(ApiKey.org_id == org_id, ApiKey.is_active.is_(True))
        .order_by(ApiKey.created_at.asc())
        .limit(1)
    )

    # Determine subnet netuids from adapter registry or static fallback
    registry: AdapterRegistry | None = getattr(
        request.app.state, "adapter_registry", None
    )
    netuids: list[int] = (
        [info.config.netuid for info in registry.list_all()]
        if registry is not None
        else [1, 19, 62]
    )

    subnets: list[SubnetOverview] = []
    for netuid in netuids:
        limits = get_subnet_rate_limits(netuid)
        subnets.append(
            SubnetOverview(
                name=_SUBNET_NAMES.get(netuid, f"Subnet {netuid}"),
                netuid=netuid,
                status=_get_subnet_status(request, netuid),
                rate_limits=SubnetRateLimits(
                    minute=limits.get("minute", 0),
                    day=limits.get("day", 0),
                    month=limits.get("month", 0),
                ),
            )
        )

    logger.info("dashboard_overview_loaded", org_id=str(org_id))

    return OverviewResponse(
        email=org.email,
        tier="free",
        created_at=org.created_at,
        api_key_count=api_key_count,
        first_api_key_prefix=first_key,
        subnets=subnets,
    )


@router.get("/usage", response_model=DashboardUsageResponse)
async def get_dashboard_usage(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    subnet: str | None = Query(default=None, description="Filter by subnet name"),
    start_date: date | None = Query(default=None, description="Start date (ISO 8601)"),
    end_date: date | None = Query(default=None, description="End date (ISO 8601)"),
    granularity: Literal["daily", "monthly"] = Query(default="daily"),
) -> DashboardUsageResponse:
    """Return per-subnet usage with quota info for the dashboard."""
    today = datetime.now(UTC).date()
    effective_start = start_date or (today - timedelta(days=30))
    effective_end = end_date or today

    subnets = await get_usage_summaries(
        db=db,
        org_id=org_id,
        start_date=effective_start,
        end_date=effective_end,
        granularity=granularity,
        subnet_filter=subnet,
    )

    # Attach quota info to each subnet
    quotas = await get_quota_status(db=db, org_id=org_id)
    quota_map = {q.netuid: q for q in quotas}
    for subnet_usage in subnets:
        subnet_usage.quota = quota_map.get(subnet_usage.netuid)

    logger.info("dashboard_usage_loaded", org_id=str(org_id), subnet=subnet)

    return DashboardUsageResponse(
        start_date=effective_start,
        end_date=effective_end,
        granularity=granularity,
        subnets=subnets,
    )
