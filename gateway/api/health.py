import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
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
# connection pool under flood.  Only healthy responses are cached so that
# recovery is detected immediately.
_health_cache: dict[str, Any] = {}
_HEALTH_CACHE_TTL = 5.0


def clear_health_cache() -> None:
    """Clear cached health state. Used by test fixtures."""
    _health_cache.clear()


@router.get("/v1/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    now = time.monotonic()
    cached_time = _health_cache.get("time")
    if cached_time is not None and now - cached_time < _HEALTH_CACHE_TTL:
        cached_result: HealthResponse = _health_cache["result"]
        return JSONResponse(content=cached_result.model_dump(), status_code=200)

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

    is_healthy = db_status == redis_status == "healthy"
    overall = "healthy" if is_healthy else "degraded"
    result = HealthResponse(
        status=overall,
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
    )

    # Only cache healthy responses so degraded state is not sticky
    if is_healthy:
        _health_cache["result"] = result
        _health_cache["time"] = now
    else:
        _health_cache.clear()

    status_code = 200 if is_healthy else 503
    return JSONResponse(content=result.model_dump(), status_code=status_code)
