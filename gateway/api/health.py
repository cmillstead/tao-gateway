import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from gateway.core.database import get_session_factory
from gateway.core.redis import try_get_redis
from gateway.schemas.health import SubnetHealthStatus

if TYPE_CHECKING:
    from gateway.routing.metagraph_sync import MetagraphManager

logger = structlog.get_logger()
router = APIRouter()

# In-memory cache prevents the health endpoint from being used as a DDoS
# vector — each call makes DB + Redis round-trips that could exhaust the
# connection pool under flood.  Only healthy responses are cached so that
# recovery is detected immediately.
# Note: concurrent requests may all miss the cache simultaneously before one
# populates it — this is a benign race in single-threaded asyncio and self-heals
# once the first response completes.
_health_cache: dict[str, Any] = {}
_HEALTH_CACHE_TTL = 5.0

_SYNC_ERROR_CATEGORIES: dict[str, str] = {
    "timeout": "timeout",
    "timed out": "timeout",
    "connection": "connection_error",
    "unreachable": "connection_error",
    "refused": "connection_error",
    "reset": "connection_error",
    "ssl": "ssl_error",
    "certificate": "ssl_error",
    "dns": "dns_error",
    "resolve": "dns_error",
    "authentication": "auth_error",
    "permission": "auth_error",
}


def _sanitize_sync_error(raw_error: str | None) -> str | None:
    """Categorize raw exception strings to avoid leaking internal details."""
    if raw_error is None:
        return None
    lower = raw_error.lower()
    for keyword, category in _SYNC_ERROR_CATEGORIES.items():
        if keyword in lower:
            return category
    return "sync_error"


def clear_health_cache() -> None:
    """Clear cached health state. Used by test fixtures."""
    _health_cache.clear()


def _get_metagraph_status(request: Request) -> dict[str, SubnetHealthStatus] | None:
    """Extract metagraph sync status from app.state if available."""
    mgr: MetagraphManager | None = getattr(
        request.app.state, "metagraph_manager", None
    )
    if mgr is None:
        return None

    all_states = mgr.get_all_states()
    if not all_states:
        return None

    result: dict[str, SubnetHealthStatus] = {}
    for netuid, state in all_states.items():
        last_sync: str | None = None
        if state.last_sync_time > 0:
            last_sync = datetime.fromtimestamp(
                state.last_sync_time, tz=UTC
            ).isoformat()
        result[f"sn{netuid}"] = SubnetHealthStatus(
            netuid=netuid,
            last_sync=last_sync,
            is_stale=state.is_stale,
            sync_error=_sanitize_sync_error(state.last_sync_error),
        )
    return result



@router.get("/v1/health")
async def health_check(
    request: Request,
) -> JSONResponse:
    now = time.monotonic()
    cached_time = _health_cache.get("time")
    if cached_time is not None and now - cached_time < _HEALTH_CACHE_TTL:
        return JSONResponse(content=_health_cache["result"], status_code=200)

    db_status = "healthy"
    redis_status = "healthy"

    try:
        async with get_session_factory()() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
        logger.warning("health_check_db_failed")

    redis = await try_get_redis()
    if redis is None:
        redis_status = "unhealthy"
        logger.warning("health_check_redis_failed")
    else:
        try:
            await redis.ping()  # type: ignore[misc]
        except Exception:
            redis_status = "unhealthy"
            logger.warning("health_check_redis_failed")

    metagraph_status = _get_metagraph_status(request)
    metagraph_stale = False
    if metagraph_status:
        metagraph_stale = any(s.is_stale for s in metagraph_status.values())

    is_healthy = db_status == redis_status == "healthy" and not metagraph_stale
    overall = "healthy" if is_healthy else "degraded"
    status_code = 200 if is_healthy else 503

    # Public response: only expose top-level status, not component details
    public_result = {"status": overall}

    # Only cache healthy responses so degraded state is not sticky.
    if is_healthy:
        _health_cache["result"] = public_result
        _health_cache["time"] = now
    else:
        _health_cache.clear()

    return JSONResponse(content=public_result, status_code=status_code)
