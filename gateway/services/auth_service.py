import contextlib
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import jwt
import structlog
from argon2.exceptions import VerifyMismatchError
from jwt.exceptions import PyJWTError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.config import settings
from gateway.core.exceptions import AuthenticationError
from gateway.core.security import ph, try_rehash
from gateway.models.organization import Organization
from gateway.models.refresh_token import RefreshToken

logger = structlog.get_logger()

# Pre-computed dummy hash for constant-time login rejection.
# Prevents timing attacks that reveal whether an email is registered.
_DUMMY_HASH = ph.hash("dummy-password-for-timing-equalization")


async def get_org_by_id(org_id: str, db: AsyncSession) -> Organization | None:
    result: Organization | None = await db.scalar(
        select(Organization).where(Organization.id == org_id)
    )
    return result


async def signup(email: str, password: str, db: AsyncSession) -> Organization:
    email = email.lower().strip()
    password_hash = ph.hash(password)
    org = Organization(email=email, password_hash=password_hash)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def login(email: str, password: str, db: AsyncSession) -> str:
    email = email.lower().strip()
    org = await db.scalar(select(Organization).where(Organization.email == email))
    if org is None:
        # Run argon2 verify against dummy hash to equalize timing with the
        # "valid email, wrong password" path — prevents email enumeration.
        with contextlib.suppress(VerifyMismatchError):
            ph.verify(_DUMMY_HASH, password)
        raise AuthenticationError("Invalid credentials")
    try:
        ph.verify(org.password_hash, password)
    except VerifyMismatchError as exc:
        raise AuthenticationError("Invalid credentials") from exc

    # Best-effort rehash — don't fail login if this errors
    await try_rehash(db, org, "password_hash", password)

    return create_jwt_token(str(org.id))


async def login_with_org_id(
    email: str, password: str, db: AsyncSession
) -> tuple[str, str]:
    """Login and return (jwt_token, org_id) — avoids decode round-trip."""
    email = email.lower().strip()
    org = await db.scalar(select(Organization).where(Organization.email == email))
    if org is None:
        with contextlib.suppress(VerifyMismatchError):
            ph.verify(_DUMMY_HASH, password)
        raise AuthenticationError("Invalid credentials")
    try:
        ph.verify(org.password_hash, password)
    except VerifyMismatchError as exc:
        raise AuthenticationError("Invalid credentials") from exc

    await try_rehash(db, org, "password_hash", password)

    org_id = str(org.id)
    return create_jwt_token(org_id), org_id


_JWT_ISSUER = "tao-gateway"
_JWT_AUDIENCE = "tao-gateway-dashboard"


def create_jwt_token(org_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": org_id,
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_jwt_token(token: str) -> str:
    """Returns org_id string or raises AuthenticationError."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=_JWT_ISSUER,
            audience=_JWT_AUDIENCE,
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise AuthenticationError("Invalid token")
        return sub
    except PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc


def _hash_refresh_token(token: str) -> str:
    """Hash a refresh token using SHA-256 for storage.

    Refresh tokens are high-entropy random strings so SHA-256 is sufficient
    (unlike passwords, they don't need argon2).
    """
    return sha256(token.encode()).hexdigest()


async def create_refresh_token(org_id: str, db: AsyncSession) -> str:
    """Create a new refresh token and persist it. Returns the raw token."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_refresh_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    record = RefreshToken(
        token_hash=token_hash,
        org_id=org_id,
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()
    return raw_token


async def rotate_refresh_token(old_token: str, db: AsyncSession) -> tuple[str, str]:
    """Validate and rotate a refresh token.

    Returns (new_jwt, new_refresh_token).
    Raises AuthenticationError if the token is invalid/expired/revoked.
    """
    old_hash = _hash_refresh_token(old_token)
    record = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == old_hash)
        .with_for_update()
    )
    if record is None:
        raise AuthenticationError("Invalid refresh token")
    if record.revoked_at is not None:
        raise AuthenticationError("Refresh token has been revoked")
    if record.expires_at < datetime.now(UTC):
        raise AuthenticationError("Refresh token has expired")

    # Revoke the old token (rotation)
    now = datetime.now(UTC)
    record.revoked_at = now

    # Opportunistic cleanup: delete expired/revoked tokens for this org
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.org_id == record.org_id,
            (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.isnot(None)),
            RefreshToken.id != record.id,  # keep the one we just revoked until commit
        )
    )
    await db.commit()

    org_id = str(record.org_id)
    new_jwt = create_jwt_token(org_id)
    new_refresh = await create_refresh_token(org_id, db)
    logger.info("refresh_token_rotated", org_id=org_id)
    return new_jwt, new_refresh


async def revoke_refresh_token(token: str, db: AsyncSession) -> None:
    """Revoke a refresh token (logout)."""
    token_hash = _hash_refresh_token(token)
    record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await db.commit()
