import contextlib
from datetime import UTC, datetime, timedelta

import jwt
from argon2.exceptions import VerifyMismatchError
from jwt.exceptions import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.config import settings
from gateway.core.exceptions import AuthenticationError
from gateway.core.security import ph, try_rehash
from gateway.models.organization import Organization

# Pre-computed dummy hash for constant-time login rejection.
# Prevents timing attacks that reveal whether an email is registered.
_DUMMY_HASH = ph.hash("dummy-password-for-timing-equalization")


async def signup(email: str, password: str, db: AsyncSession) -> Organization:
    password_hash = ph.hash(password)
    org = Organization(email=email, password_hash=password_hash)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def login(email: str, password: str, db: AsyncSession) -> str:
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
