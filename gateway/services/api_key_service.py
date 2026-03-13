import secrets
import uuid
from typing import Literal

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.exceptions import GatewayError
from gateway.core.security import ph
from gateway.models.api_key import ApiKey

logger = structlog.get_logger()

Environment = Literal["live", "test"]

API_KEY_PREFIX_LENGTH = 20
MAX_KEYS_PER_ORG = 50
_REVOCATION_TOMBSTONE_TTL = 120


def generate_api_key(env: Environment = "live") -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, key_hash)."""
    random_suffix = secrets.token_urlsafe(20)
    full_key = f"tao_sk_{env}_{random_suffix}"
    prefix = full_key[:API_KEY_PREFIX_LENGTH]
    key_hash = ph.hash(full_key)
    return full_key, prefix, key_hash


async def create_api_key(
    org_id: uuid.UUID, env: Environment, db: AsyncSession
) -> tuple[ApiKey, str]:
    """Create and persist a new API key. Returns (api_key_record, full_key)."""
    # Enforce per-org key limit
    active_count = await db.scalar(
        select(func.count()).select_from(ApiKey).where(
            ApiKey.org_id == org_id, ApiKey.is_active.is_(True)
        )
    )
    if active_count is not None and active_count >= MAX_KEYS_PER_ORG:
        raise GatewayError(
            f"Maximum of {MAX_KEYS_PER_ORG} active API keys per organization",
            status_code=422,
            error_type="validation_error",
        )

    full_key, prefix, key_hash = generate_api_key(env)
    api_key = ApiKey(org_id=org_id, prefix=prefix, key_hash=key_hash)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, full_key


async def list_api_keys(
    org_id: uuid.UUID, db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[ApiKey], int]:
    """List API keys for an organization with pagination. Returns (keys, total_count)."""
    total = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.org_id == org_id)
    ) or 0
    result = await db.scalars(
        select(ApiKey)
        .where(ApiKey.org_id == org_id)
        .order_by(ApiKey.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all()), total


async def revoke_api_key(
    key_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession, redis: Redis | None
) -> ApiKey | None:
    """Revoke an API key and invalidate its Redis cache entry.

    Sets a separate tombstone key so concurrent auth requests that
    re-populate the cache cannot overwrite the revocation signal.
    Gracefully handles Redis being unavailable.
    """
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.id == key_id, ApiKey.org_id == org_id, ApiKey.is_active.is_(True)
        )
    )
    if key is None:
        return None

    key.is_active = False
    await db.commit()
    await db.refresh(key)

    # Best-effort cache invalidation — revocation is DB-authoritative.
    if redis is not None:
        cache_key = f"api_key:{key.prefix}"
        tombstone_key = f"api_key_revoked:{key.prefix}"
        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.set(tombstone_key, "1", ex=_REVOCATION_TOMBSTONE_TTL)
                pipe.delete(cache_key)
                await pipe.execute()
        except Exception:
            logger.warning("revoke_cache_tombstone_failed", key_id=str(key_id))

    return key
