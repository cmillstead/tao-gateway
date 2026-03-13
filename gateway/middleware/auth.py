import uuid
from dataclasses import dataclass

import structlog
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.exceptions import AuthenticationError
from gateway.core.redis import get_redis
from gateway.core.security import ph
from gateway.models.api_key import ApiKey
from gateway.services.api_key_service import API_KEY_PREFIX_LENGTH
from gateway.services.auth_service import verify_jwt_token

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class ApiKeyInfo:
    """Validated API key context passed to downstream handlers."""

    key_id: uuid.UUID
    org_id: uuid.UUID


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiKeyInfo:
    """Validate Bearer API key, return key info. Uses Redis 60s TTL cache."""
    if credentials is None:
        raise AuthenticationError("Missing authorization header")

    token = credentials.credentials
    prefix = token[:API_KEY_PREFIX_LENGTH]
    cache_key = f"api_key:{prefix}"

    # Check for revocation tombstone first
    cached = await redis.get(cache_key)
    if cached is not None:
        try:
            cached_str = cached.decode()
        except UnicodeDecodeError:
            logger.warning("api_key_cache_corrupt", prefix=prefix[:12] + "****")
            await redis.delete(cache_key)
            cached_str = None

        if cached_str == "__revoked__":
            raise AuthenticationError("Invalid API key")

        # Cache stores key_hash:key_id:org_id — always verify hash even on hit
        if cached_str is not None:
            try:
                cached_hash, key_id_str, org_id_str = cached_str.split(":", 2)
                ph.verify(cached_hash, token)
                return ApiKeyInfo(key_id=uuid.UUID(key_id_str), org_id=uuid.UUID(org_id_str))
            except VerifyMismatchError as exc:
                logger.warning("api_key_hash_mismatch", prefix=prefix[:12] + "****")
                raise AuthenticationError("Invalid API key") from exc
            except (ValueError, IndexError):
                logger.warning("api_key_cache_corrupt", prefix=prefix[:12] + "****")
                await redis.delete(cache_key)

    # Cache miss — look up in DB
    key_record = await db.scalar(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.is_active.is_(True),
        )
    )
    if key_record is None:
        logger.warning("api_key_not_found", prefix=prefix[:12] + "****")
        raise AuthenticationError("Invalid API key")

    try:
        ph.verify(key_record.key_hash, token)
    except VerifyMismatchError as exc:
        logger.warning("api_key_hash_mismatch", prefix=prefix[:12] + "****")
        raise AuthenticationError("Invalid API key") from exc

    # Best-effort rehash — don't fail the request if this errors
    current_hash = key_record.key_hash
    try:
        if ph.check_needs_rehash(key_record.key_hash):
            current_hash = ph.hash(token)
            key_record.key_hash = current_hash
            await db.commit()
    except Exception:
        logger.warning("api_key_rehash_failed", prefix=prefix[:12] + "****")
        await db.rollback()

    # Cache: key_hash:key_id:org_id — hash included so cache hits still verify
    cache_value = f"{current_hash}:{key_record.id}:{key_record.org_id}"
    await redis.set(cache_key, cache_value, ex=60)
    return ApiKeyInfo(key_id=key_record.id, org_id=key_record.org_id)


async def get_current_org_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID:
    """Validate JWT token, return org_id. Used for dashboard endpoints."""
    if credentials is None:
        raise AuthenticationError("Missing authorization header")

    org_id_str = verify_jwt_token(credentials.credentials)
    try:
        return uuid.UUID(org_id_str)
    except ValueError as exc:
        raise AuthenticationError("Invalid token") from exc
