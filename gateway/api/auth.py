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


async def _rate_limit_auth(
    request: Request,
) -> None:
    """Fixed-window per-IP rate limit on auth endpoints.

    Fails open if Redis is unavailable — rate limiting is a best-effort
    defense, not a hard gate.  Blocking all auth when Redis is down would
    be worse than temporarily allowing unthrottled requests.
    """
    direct_ip = request.client.host if request.client else None
    if direct_ip is None:
        # Cannot rate-limit without a client IP — skip rather than
        # sharing a single bucket for all unknown clients.
        return
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and direct_ip in settings.trusted_proxies:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = direct_ip
    key = f"auth_rate:{client_ip}"
    try:
        redis = await get_redis()
        # Uses Redis EVAL command for server-side Lua execution (not Python eval)
        raw_result = await redis.eval(  # type: ignore[misc]
            _RATE_LIMIT_LUA, 1, key, 60
        )
        current = int(raw_result)
    except Exception:
        logger.warning("rate_limit_redis_unavailable", client_ip=client_ip)
        await reset_redis()
        return
    if current > settings.auth_rate_limit_per_minute:
        raise RateLimitExceededError("Too many authentication attempts. Try again later.")


router = APIRouter(dependencies=[Depends(_rate_limit_auth)])


@router.post("/signup", status_code=HTTP_201_CREATED, response_model=SignupResponse)
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)) -> SignupResponse:
    try:
        org = await auth_service.signup(request.email, request.password, db)
    except IntegrityError as exc:
        await db.rollback()
        raise GatewayError(
            "Email already registered", status_code=409, error_type="conflict"
        ) from exc
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
