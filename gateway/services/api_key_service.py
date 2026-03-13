import secrets
import uuid
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.security import ph
from gateway.models.api_key import ApiKey

Environment = Literal["live", "test"]


def generate_api_key(env: Environment = "live") -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, key_hash)."""
    random_suffix = secrets.token_urlsafe(20)
    full_key = f"tao_sk_{env}_{random_suffix}"
    prefix = full_key[:20]
    key_hash = ph.hash(full_key)
    return full_key, prefix, key_hash


async def create_api_key(
    org_id: uuid.UUID, env: Environment, db: AsyncSession
) -> tuple[ApiKey, str]:
    """Create and persist a new API key. Returns (api_key_record, full_key)."""
    full_key, prefix, key_hash = generate_api_key(env)
    api_key = ApiKey(org_id=org_id, prefix=prefix, key_hash=key_hash)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, full_key


async def list_api_keys(org_id: uuid.UUID, db: AsyncSession) -> list[ApiKey]:
    """List all API keys for an organization."""
    result = await db.scalars(select(ApiKey).where(ApiKey.org_id == org_id))
    return list(result.all())


async def revoke_api_key(
    key_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession, redis: Redis
) -> ApiKey | None:
    """Revoke an API key and invalidate its Redis cache entry."""
    key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
    )
    if key is None:
        return None
    key.is_active = False
    await redis.delete(f"api_key:{key.prefix}")
    await db.commit()
    await db.refresh(key)
    return key
