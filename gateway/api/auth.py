import ipaddress
import uuid
from typing import Literal

import structlog
from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.config import settings
from gateway.core.database import get_db
from gateway.core.exceptions import AuthenticationError, GatewayError, RateLimitExceededError
from gateway.core.rate_limit import check_rate_limit
from gateway.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from gateway.services import auth_service

_COOKIE_HTTPONLY = True
_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
_COOKIE_PATH = "/"

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


def _set_auth_cookies(
    response: JSONResponse, access_token: str, refresh_token: str
) -> None:
    secure = not settings.debug
    max_age_access = settings.jwt_expire_minutes * 60
    max_age_refresh = settings.refresh_token_expire_days * 86400
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=_COOKIE_HTTPONLY,
        secure=secure,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
        max_age=max_age_access,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=_COOKIE_HTTPONLY,
        secure=secure,
        samesite=_COOKIE_SAMESITE,
        path="/auth",
        max_age=max_age_refresh,
    )


def _clear_auth_cookies(response: JSONResponse) -> None:
    response.delete_cookie(key="access_token", path=_COOKIE_PATH)
    response.delete_cookie(key="refresh_token", path="/auth")


@router.post("/login/dashboard")
async def login_dashboard(
    request: LoginRequest, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Dashboard login — sets JWT and refresh token as httpOnly cookies."""
    try:
        access_token, org_id = await auth_service.login_with_org_id(
            request.email, request.password, db
        )
    except GatewayError:
        logger.info("dashboard_login_failed")
        raise

    refresh_token = await auth_service.create_refresh_token(org_id, db)
    response = JSONResponse(content={"message": "Login successful"})
    _set_auth_cookies(response, access_token, refresh_token)
    logger.info("dashboard_login_success")
    return response


@router.post("/refresh")
async def refresh(
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Rotate refresh token and issue new JWT cookie."""
    if refresh_token is None:
        raise AuthenticationError("Missing refresh token")

    new_jwt, new_refresh = await auth_service.rotate_refresh_token(refresh_token, db)
    response = JSONResponse(content={"message": "Token refreshed"})
    _set_auth_cookies(response, new_jwt, new_refresh)
    logger.info("token_refreshed")
    return response


@router.get("/me")
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return current user info from cookie/bearer auth. Lightweight auth check."""
    token: str | None = None
    # Check Bearer header first, then cookie
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("access_token")

    if token is None:
        raise AuthenticationError("Not authenticated")

    org_id_str = auth_service.verify_jwt_token(token)
    org = await auth_service.get_org_by_id(org_id_str, db)
    if org is None:
        raise AuthenticationError("Not authenticated")

    return JSONResponse(content={"id": str(org.id), "email": org.email})


@router.post("/logout")
async def logout(
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Revoke refresh token and clear auth cookies."""
    if refresh_token is not None:
        await auth_service.revoke_refresh_token(refresh_token, db)
    response = JSONResponse(content={"message": "Logged out"})
    _clear_auth_cookies(response)
    logger.info("logout")
    return response
