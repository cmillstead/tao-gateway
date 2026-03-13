from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from jose import jwt

from gateway.core.config import settings
from gateway.core.exceptions import AuthenticationError
from gateway.services.auth_service import create_jwt_token, verify_jwt_token

ph = PasswordHasher()


def test_password_hashing_round_trip() -> None:
    password = "secure-password-123"
    hashed = ph.hash(password)
    assert hashed != password
    assert ph.verify(hashed, password)


def test_jwt_create_and_verify() -> None:
    org_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_jwt_token(org_id)
    assert isinstance(token, str)
    assert len(token) > 0
    result = verify_jwt_token(token)
    assert result == org_id


def test_jwt_contains_iat_claim() -> None:
    org_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_jwt_token(org_id)
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert "iat" in payload
    assert "exp" in payload
    assert "sub" in payload
    assert payload["iat"] <= payload["exp"]


def test_jwt_verify_invalid_token() -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        verify_jwt_token("invalid.token.value")
    assert exc_info.value.status_code == 401


def test_jwt_verify_empty_token() -> None:
    with pytest.raises(AuthenticationError) as exc_info:
        verify_jwt_token("")
    assert exc_info.value.status_code == 401


def test_jwt_verify_expired_token() -> None:
    """Expired JWT is rejected with AuthenticationError."""
    expired_payload = {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(AuthenticationError) as exc_info:
        verify_jwt_token(token)
    assert exc_info.value.status_code == 401
