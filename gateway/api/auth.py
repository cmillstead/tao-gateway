import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.config import settings
from gateway.core.database import get_db
from gateway.core.exceptions import GatewayError, RateLimitExceededError
from gateway.core.redis import get_redis, reset_redis
from gateway.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from gateway.services import auth_service

logger = structlog.get_logger()

# Lua script: INCR the counter and set EXPIRE only when the key is first
# created (INCR returns 1).  This gives a true fixed-window rate limit
# instead of resetting the TTL on every request.
_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""
_rate_limit_script: Any = None
_rate_limit_script_redis: object | None = None  # track which Redis instance owns the script

# In-memory fallback rate limiter for when Redis is unavailable.
# Uses a conservative limit (10 req/min per IP) to limit abuse during outages.
_FALLBACK_LIMIT = 10
_FALLBACK_WINDOW = 60.0
_fallback_counts: dict[str, tuple[float, int]] = {}


def _check_fallback_rate_limit(client_ip: str) -> bool:
    """Return True if the request should be allowed, False if rate-limited."""
    now = time.monotonic()
    entry = _fallback_counts.get(client_ip)
    if entry is None or now - entry[0] >= _FALLBACK_WINDOW:
        _fallback_counts[client_ip] = (now, 1)
        return True
    window_start, count = entry
    if count >= _FALLBACK_LIMIT:
        return False
    _fallback_counts[client_ip] = (window_start, count + 1)
    return True


async def _rate_limit_auth(
    request: Request,
) -> None:
    """Fixed-window per-IP rate limit on auth endpoints.

    Falls back to an in-memory rate limiter when Redis is unavailable.
    """
    direct_ip = request.client.host if request.client else None
    if direct_ip is None:
        return
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and direct_ip in settings.trusted_proxies:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = direct_ip
    key = f"auth_rate:{client_ip}"
    try:
        redis = await get_redis()
        global _rate_limit_script, _rate_limit_script_redis  # noqa: PLW0603
        if _rate_limit_script is None or _rate_limit_script_redis is not redis:
            _rate_limit_script = redis.register_script(_RATE_LIMIT_LUA)
            _rate_limit_script_redis = redis
        raw_result = await _rate_limit_script(keys=[key], args=[60])
        current = int(raw_result)
    except Exception:
        logger.warning("rate_limit_redis_unavailable")
        await reset_redis()
        # Fallback to in-memory rate limiter instead of failing open
        if not _check_fallback_rate_limit(client_ip):
            raise RateLimitExceededError(
                "Too many authentication attempts. Try again later."
            ) from None
        return
    if current > settings.auth_rate_limit_per_minute:
        raise RateLimitExceededError("Too many authentication attempts. Try again later.")


router = APIRouter(dependencies=[Depends(_rate_limit_auth)])


@router.post("/signup", status_code=HTTP_201_CREATED, response_model=SignupResponse)
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)) -> SignupResponse:
    try:
        org = await auth_service.signup(request.email, request.password, db)
    except IntegrityError:
        await db.rollback()
        # Return identical response to prevent email enumeration (SEC-014)
        return SignupResponse(id="", email=request.email, message="Account created successfully")
    logger.info("org_created", org_id=str(org.id))
    return SignupResponse(id=str(org.id), email=org.email, message="Account created successfully")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    try:
        token = await auth_service.login(request.email, request.password, db)
    except GatewayError:
        logger.info("login_failed")
        raise
    logger.info("login_success")
    return LoginResponse(access_token=token)
