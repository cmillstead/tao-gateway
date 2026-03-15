import uuid
from dataclasses import dataclass

import structlog
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.database import get_db
from gateway.core.exceptions import AuthenticationError
from gateway.core.redis import try_get_redis
from gateway.core.security import ph, try_rehash
from gateway.models.api_key import ApiKey
from gateway.services.api_key_service import API_KEY_CACHE_TTL, API_KEY_PREFIX_LENGTH
from gateway.services.auth_service import verify_jwt_token

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class ApiKeyInfo:
    """Validated API key context passed to downstream handlers."""

    key_id: uuid.UUID
    org_id: uuid.UUID
    debug_mode: bool = False


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyInfo:
    """Validate Bearer API key, return key info.

    Uses Redis 60s TTL cache when available; falls through to DB-only
    validation when Redis is down so that API-key-protected endpoints
    degrade gracefully instead of returning 500.
    """
    if credentials is None:
        raise AuthenticationError("Missing authorization header")

    token = credentials.credentials
    prefix = token[:API_KEY_PREFIX_LENGTH]
    redacted = prefix[:12] + "****"
    cache_key = f"api_key:{prefix}"

    redis = await try_get_redis(reset_on_failure=True)
    tombstone_key = f"api_key_revoked:{prefix}"

    # Check Redis cache (tombstone + cached credentials)
    if redis is not None:
        # Check separate tombstone key first — cannot be overwritten by
        # concurrent cache population, preventing the TOCTOU race.
        try:
            if await redis.exists(tombstone_key):
                raise AuthenticationError("Invalid API key")
        except AuthenticationError:
            raise
        except Exception:
            logger.warning("redis_tombstone_check_failed", prefix=redacted)

        try:
            cached = await redis.get(cache_key)
        except Exception:
            logger.warning("redis_get_failed", prefix=redacted)
            cached = None

        if cached is not None:
            try:
                cached_str = cached.decode()
            except UnicodeDecodeError:
                logger.warning("api_key_cache_corrupt", prefix=redacted)
                await redis.delete(cache_key)
                cached_str = None

            # Cache stores key_hash:key_id:org_id:debug_mode — always verify hash even on hit
            if cached_str is not None:
                try:
                    parts = cached_str.split(":")
                    if len(parts) >= 3:
                        cached_hash = parts[0]
                        key_id_str = parts[1]
                        org_id_str = parts[2]
                        debug_mode = parts[3] == "1" if len(parts) > 3 else False
                        ph.verify(cached_hash, token)
                        return ApiKeyInfo(
                            key_id=uuid.UUID(key_id_str),
                            org_id=uuid.UUID(org_id_str),
                            debug_mode=debug_mode,
                        )
                except VerifyMismatchError as exc:
                    logger.warning("api_key_hash_mismatch", prefix=redacted)
                    raise AuthenticationError("Invalid API key") from exc
                except (ValueError, IndexError):
                    logger.warning("api_key_cache_corrupt", prefix=redacted)
                    await redis.delete(cache_key)

    # Cache miss (or Redis unavailable) — look up in DB
    key_record = await db.scalar(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.is_active.is_(True),
        )
    )
    if key_record is None:
        logger.warning("api_key_not_found", prefix=redacted)
        raise AuthenticationError("Invalid API key")

    try:
        ph.verify(key_record.key_hash, token)
    except VerifyMismatchError as exc:
        logger.warning("api_key_hash_mismatch", prefix=redacted)
        raise AuthenticationError("Invalid API key") from exc

    # Best-effort rehash — don't fail the request if this errors
    current_hash = key_record.key_hash
    await try_rehash(db, key_record, "key_hash", token)
    current_hash = key_record.key_hash  # may have been updated by rehash

    # Best-effort cache population
    debug_flag = "1" if key_record.debug_mode else "0"
    if redis is not None:
        cache_value = f"{current_hash}:{key_record.id}:{key_record.org_id}:{debug_flag}"
        try:
            await redis.set(cache_key, cache_value, ex=API_KEY_CACHE_TTL)
        except Exception:
            logger.warning("redis_set_failed", prefix=redacted)

    return ApiKeyInfo(
        key_id=key_record.id,
        org_id=key_record.org_id,
        debug_mode=key_record.debug_mode,
    )


async def get_current_org_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID:
    """Validate JWT token, return org_id. Used for dashboard endpoints.

    Checks Bearer header first (API callers), then falls back to
    httpOnly cookie (dashboard SPA).
    """
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get("access_token")

    if token is None:
        raise AuthenticationError("Missing authorization")

    org_id_str = verify_jwt_token(token)
    try:
        return uuid.UUID(org_id_str)
    except ValueError as exc:
        raise AuthenticationError("Invalid token") from exc
