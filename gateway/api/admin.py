"""Operator admin endpoints (FR37-40). Hidden from public OpenAPI docs."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request

from gateway.api.health import _sanitize_sync_error
from gateway.core.database import get_db
from gateway.middleware.auth import require_admin
from gateway.schemas.admin import (
    DeveloperMetrics,
    MetagraphResponse,
    MetricsResponse,
    MinerInfo,
    MinerResponse,
    SubnetMetagraphStatus,
)
from gateway.services import admin_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from gateway.routing.metagraph_sync import MetagraphManager
    from gateway.routing.scorer import MinerScorer

router = APIRouter()


@router.get("/metrics")
async def get_metrics(
    time_range: str = Query("24h", pattern=r"^(1h|24h|7d|30d)$"),
    _admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    return await admin_service.get_system_metrics(db, time_range)


@router.get("/metagraph")
async def get_metagraph(
    request: Request,
    _admin_id: uuid.UUID = Depends(require_admin),
) -> MetagraphResponse:
    mgr: MetagraphManager | None = getattr(
        request.app.state, "metagraph_manager", None
    )
    if mgr is None:
        return MetagraphResponse(subnets=[])

    all_states = mgr.get_all_states()
    subnets: list[SubnetMetagraphStatus] = []

    for netuid, state in all_states.items():
        last_sync: str | None = None
        if state.last_sync_time > 0:
            last_sync = datetime.fromtimestamp(
                state.last_sync_time, tz=UTC
            ).isoformat()

        staleness = (
            time.monotonic() - state.last_sync_mono
            if state.last_sync_mono >= 0
            else -1.0  # -1 signals "never synced"
        )

        if state.metagraph is None:
            sync_status = "never_synced"
        elif state.is_stale:
            sync_status = "degraded"
        else:
            sync_status = "healthy"

        active_miners = 0
        if state.metagraph is not None:
            try:
                incentives = state.metagraph.I
                active_miners = int(sum(1 for i in incentives if float(i) > 0))
            except Exception:
                active_miners = int(state.metagraph.n)

        subnets.append(
            SubnetMetagraphStatus(
                netuid=netuid,
                subnet_name=f"sn{netuid}",
                last_sync_time=last_sync,
                staleness_seconds=round(staleness, 1),
                is_stale=state.is_stale,
                sync_status=sync_status,
                last_sync_error=_sanitize_sync_error(state.last_sync_error),
                consecutive_failures=state.consecutive_failures,
                active_miners=active_miners,
            )
        )

    return MetagraphResponse(subnets=sorted(subnets, key=lambda s: s.netuid))


@router.get("/developers")
async def get_developers(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeveloperMetrics:
    return await admin_service.get_developer_metrics(db, limit=limit, offset=offset)


@router.get("/miners")
async def get_miners(
    request: Request,
    netuid: int | None = Query(None),
    _admin_id: uuid.UUID = Depends(require_admin),
) -> MinerResponse:
    scorer: MinerScorer | None = getattr(request.app.state, "scorer", None)
    mgr: MetagraphManager | None = getattr(
        request.app.state, "metagraph_manager", None
    )

    if scorer is None or mgr is None:
        return MinerResponse(subnets={})

    all_states = mgr.get_all_states()
    netuids = [netuid] if netuid is not None else list(all_states.keys())

    result: dict[str, list[MinerInfo]] = {}

    for net in netuids:
        subnet_name = f"sn{net}"
        miner_details = scorer.get_miner_details(net)

        # Build incentive lookup from metagraph
        incentive_map: dict[int, float] = {}
        state = all_states.get(net)
        if state is not None and state.metagraph is not None:
            try:
                for uid_idx in range(int(state.metagraph.n)):
                    incentive_map[uid_idx] = float(state.metagraph.I[uid_idx])
            except Exception:
                pass

        miners: list[MinerInfo] = []
        for detail in miner_details:
            error_rate = (
                (detail.total_requests - detail.successful_requests) / detail.total_requests
                if detail.total_requests > 0
                else 0.0
            )
            miners.append(
                MinerInfo(
                    miner_uid=detail.miner_uid,
                    hotkey_prefix=detail.hotkey[:8],
                    netuid=net,
                    subnet_name=subnet_name,
                    incentive_score=incentive_map.get(detail.miner_uid, 0.0),
                    gateway_quality_score=round(detail.quality_score, 4),
                    total_requests=detail.total_requests,
                    successful_requests=detail.successful_requests,
                    avg_latency_ms=round(detail.avg_latency_ms, 1),
                    error_rate=round(error_rate, 4),
                )
            )

        if miners:
            result[subnet_name] = sorted(
                miners, key=lambda m: m.gateway_quality_score, reverse=True
            )

    return MinerResponse(subnets=result)
