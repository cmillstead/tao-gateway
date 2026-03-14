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
                client = Redis.from_url(
                    settings.redis_url, max_connections=settings.redis_max_connections
                )
                await client.ping()  # type: ignore[misc]
                redis_client = client
            except Exception:
                _last_failure_time = time.monotonic()
                # Log only host portion — never credentials
                url = settings.redis_url
                safe_url = url.split("@")[-1] if "@" in url else url.split("//")[-1]
                logger.error("redis_connection_failed", redis_host=safe_url)
                raise
    return redis_client


async def _close_client(*, suppress_errors: bool) -> None:
    """Internal helper to close and clear the cached Redis client."""
    global redis_client  # noqa: PLW0603
    async with _redis_lock:
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                if not suppress_errors:
                    raise
            redis_client = None


async def reset_redis() -> None:
    """Reset the cached client so the next call to get_redis() reconnects.

    Call this when a Redis operation fails with a connection error to
    trigger reconnection on the next request instead of returning a
    broken client forever.
    """
    await _close_client(suppress_errors=True)


async def close_redis() -> None:
    await _close_client(suppress_errors=False)


async def try_get_redis(*, reset_on_failure: bool = False) -> Redis | None:
    """Best-effort Redis connection. Returns None when unavailable.

    When reset_on_failure is True, resets the cached client on failure so
    the next request triggers a fresh reconnection attempt.
    """
    try:
        return await get_redis()
    except Exception:
        logger.warning("redis_unavailable")
        if reset_on_failure:
            await reset_redis()
        return None
