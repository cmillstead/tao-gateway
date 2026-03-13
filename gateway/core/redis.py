import asyncio
import time

import structlog
from redis.asyncio import Redis

from gateway.core.config import settings

logger = structlog.get_logger()

redis_client: Redis | None = None
_redis_lock = asyncio.Lock()

# Circuit breaker: after a connection failure, skip retries for this many seconds
_CIRCUIT_BREAKER_COOLDOWN = 5.0
_last_failure_time: float = 0.0


async def get_redis() -> Redis:
    global redis_client, _last_failure_time  # noqa: PLW0603
    if redis_client is not None:
        return redis_client

    # Circuit breaker: fail fast if we recently failed
    now = time.monotonic()
    if now - _last_failure_time < _CIRCUIT_BREAKER_COOLDOWN:
        raise ConnectionError("Redis unavailable (circuit breaker open)")

    async with _redis_lock:
        if redis_client is None:
            try:
                client = Redis.from_url(settings.redis_url, max_connections=20)
                await client.ping()  # type: ignore[misc]
                redis_client = client
            except Exception:
                _last_failure_time = time.monotonic()
                logger.error("redis_connection_failed", redis_url=settings.redis_url[:20] + "****")
                raise
    return redis_client


async def close_redis() -> None:
    global redis_client  # noqa: PLW0603
    async with _redis_lock:
        if redis_client is not None:
            await redis_client.aclose()
            redis_client = None
