import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.config import settings
from gateway.core.database import get_db
from gateway.core.redis import get_redis
from gateway.schemas.health import HealthResponse

logger = structlog.get_logger()
router = APIRouter()

# In-memory cache prevents the health endpoint from being used as a DDoS
# vector — each call makes DB + Redis round-trips that could exhaust the
# connection pool under flood.  Cache ensures those calls happen at most
# once every _HEALTH_CACHE_TTL seconds.
_health_cache: dict[str, Any] = {}
_HEALTH_CACHE_TTL = 5.0


def clear_health_cache() -> None:
    """Clear cached health state. Used by test fixtures."""
    _health_cache.clear()


@router.get("/v1/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    now = time.monotonic()
    cached_time = _health_cache.get("time")
    if cached_time is not None and now - cached_time < _HEALTH_CACHE_TTL:
        cached_result: HealthResponse = _health_cache["result"]
        return cached_result

    db_status = "healthy"
    redis_status = "healthy"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
        logger.warning("health_check_db_failed")

    try:
        await redis.ping()  # type: ignore[misc]
    except Exception:
        redis_status = "unhealthy"
        logger.warning("health_check_redis_failed")

    overall = "healthy" if db_status == redis_status == "healthy" else "degraded"
    result = HealthResponse(
        status=overall,
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
    )
    _health_cache["result"] = result
    _health_cache["time"] = now
    return result
