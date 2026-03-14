import ipaddress
import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.config import settings
from gateway.core.database import get_db
from gateway.core.exceptions import GatewayError, RateLimitExceededError
from gateway.core.rate_limit import check_rate_limit
from gateway.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from gateway.services import auth_service

logger = structlog.get_logger()


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
        # Walk right-to-left; skip trusted proxies to find the real client IP.
        # The rightmost non-trusted IP is the one added by the last trusted proxy.
        parts = [ip.strip() for ip in forwarded_for.split(",")]
        client_ip = direct_ip  # fallback if all IPs are trusted
        for ip in reversed(parts):
            if ip not in settings.trusted_proxies:
                client_ip = ip
                break
    else:
        client_ip = direct_ip
    # Normalize IP to prevent rate limit bypass via equivalent representations
    # (e.g., ::ffff:127.0.0.1 vs 127.0.0.1, or expanded vs compressed IPv6)
    try:
        addr = ipaddress.ip_address(client_ip)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            client_ip = str(addr.ipv4_mapped)
        else:
            client_ip = str(addr)
    except ValueError:
        pass  # keep original string if not a valid IP
    key = f"auth_rate:{client_ip}"
    result = await check_rate_limit(
        key=key,
        limit=settings.auth_rate_limit_per_minute,
        window_seconds=60,
        fallback_limit=settings.auth_rate_limit_per_minute,
        log_prefix="auth_rate_limit",
    )
    if result == -1:
        raise RateLimitExceededError(
            "Too many authentication attempts. Try again later."
        )
    if result is not None and result > settings.auth_rate_limit_per_minute:
        raise RateLimitExceededError("Too many authentication attempts. Try again later.")


router = APIRouter(dependencies=[Depends(_rate_limit_auth)])


@router.post("/signup", status_code=HTTP_201_CREATED, response_model=SignupResponse)
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)) -> SignupResponse:
    try:
        org = await auth_service.signup(request.email, request.password, db)
    except IntegrityError:
        await db.rollback()
        # Return identical response to prevent email enumeration (SEC-014)
        fake_id = str(uuid.uuid4())
        normalized_email = request.email.lower().strip()
        return SignupResponse(
            id=fake_id, email=normalized_email, message="Account created successfully"
        )
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
