from redis.asyncio import Redis

from gateway.core.config import settings

redis_client: Redis | None = None


async def get_redis() -> Redis:
    global redis_client  # noqa: PLW0603
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url)
    return redis_client


async def close_redis() -> None:
    global redis_client  # noqa: PLW0603
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
