from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from gateway.core.database import get_db
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.schemas.usage import DashboardUsageResponse
from gateway.services.usage_service import get_quota_status, get_usage_summaries

logger = structlog.get_logger()
router = APIRouter()


@router.get("/usage", response_model=DashboardUsageResponse)
async def get_usage(
    api_key: ApiKeyInfo = Depends(get_current_api_key),
    db: AsyncSession = Depends(get_db),
    subnet: str | None = Query(default=None, description="Filter by subnet name"),
    start_date: date | None = Query(default=None, description="Start date (ISO 8601)"),
    end_date: date | None = Query(default=None, description="End date (ISO 8601)"),
    granularity: Literal["daily", "monthly"] = Query(default="daily"),
) -> DashboardUsageResponse:
    """Return per-subnet usage data with quota for the authenticated key's org."""
    today = datetime.now(UTC).date()
    effective_start = start_date or (today - timedelta(days=30))
    effective_end = end_date or today

    subnets = await get_usage_summaries(
        db=db,
        org_id=api_key.org_id,
        start_date=effective_start,
        end_date=effective_end,
        granularity=granularity,
        subnet_filter=subnet,
    )

    quotas = await get_quota_status(db=db, org_id=api_key.org_id)
    quota_map = {q.netuid: q for q in quotas}
    for subnet_usage in subnets:
        subnet_usage.quota = quota_map.get(subnet_usage.netuid)

    logger.info("usage_query", org_id=str(api_key.org_id), subnet=subnet)

    return DashboardUsageResponse(
        start_date=effective_start,
        end_date=effective_end,
        granularity=granularity,
        subnets=subnets,
    )
