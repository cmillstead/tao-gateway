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


@router.get("/v1/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
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
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
    )
