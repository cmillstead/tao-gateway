from datetime import UTC, datetime, timedelta

from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.config import settings
from gateway.core.exceptions import AuthenticationError
from gateway.core.security import ph
from gateway.models.organization import Organization


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
        raise AuthenticationError("Invalid credentials")
    try:
        ph.verify(org.password_hash, password)
    except VerifyMismatchError as exc:
        raise AuthenticationError("Invalid credentials") from exc
    return create_jwt_token(str(org.id))


def create_jwt_token(org_id: str) -> str:
    payload = {
        "sub": org_id,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    token: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def verify_jwt_token(token: str) -> str:
    """Returns org_id string or raises AuthenticationError."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise AuthenticationError("Invalid token")
        return sub
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc
