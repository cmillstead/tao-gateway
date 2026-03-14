"""Tests for error handling, validation errors, and response metadata."""

import json

import pytest
from fastapi import Request
from httpx import AsyncClient

from gateway.core.exceptions import (
    AuthenticationError,
    GatewayError,
    MinerInvalidResponseError,
    MinerTimeoutError,
    RateLimitExceededError,
    SubnetUnavailableError,
)
from gateway.middleware.error_handler import gateway_exception_handler
from gateway.schemas.errors import ErrorResponse


def _fake_request() -> Request:
    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    return Request(scope)


# ---------------------------------------------------------------------------
# GatewayError handler — basic envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_500_internal_error():
    """Base GatewayError returns 500 with type: internal_error."""
    exc = GatewayError("Something broke", status_code=500)
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 500
    assert body["error"]["type"] == "internal_error"
    assert body["error"]["message"] == "Something broke"
    assert body["error"]["code"] == 500
    assert "subnet" not in body["error"]
    assert "miner_uid" not in body["error"]


@pytest.mark.asyncio
async def test_502_bad_gateway_includes_miner_uid():
    """MinerInvalidResponseError (502) includes miner_uid in body."""
    exc = MinerInvalidResponseError(miner_uid="def67890", subnet="sn1")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 502
    assert body["error"]["type"] == "bad_gateway"
    assert body["error"]["miner_uid"] == "def67890"
    assert body["error"]["subnet"] == "sn1"


@pytest.mark.asyncio
async def test_504_gateway_timeout_includes_miner_uid():
    """MinerTimeoutError (504) includes miner_uid in body."""
    exc = MinerTimeoutError(miner_uid="abc12345", subnet="sn1")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 504
    assert body["error"]["type"] == "gateway_timeout"
    assert body["error"]["miner_uid"] == "abc12345"
    assert body["error"]["subnet"] == "sn1"


@pytest.mark.asyncio
async def test_503_subnet_unavailable():
    """SubnetUnavailableError returns 503 with subnet and reason."""
    exc = SubnetUnavailableError(subnet="sn19", reason="no miners available")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["error"]["type"] == "subnet_unavailable"
    assert body["error"]["subnet"] == "sn19"
    assert body["error"]["reason"] == "no miners available"


@pytest.mark.asyncio
async def test_401_authentication_error():
    """AuthenticationError returns 401 with type: authentication_error."""
    exc = AuthenticationError("Invalid API key")
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 401
    assert body["error"]["type"] == "authentication_error"
    assert body["error"]["message"] == "Invalid API key"


@pytest.mark.asyncio
async def test_429_rate_limit_error():
    """RateLimitExceededError returns 429 with subnet and retry_after."""
    exc = RateLimitExceededError(
        message="Rate limit exceeded for SN1",
        subnet="sn1",
        retry_after=12,
    )
    response = await gateway_exception_handler(_fake_request(), exc)

    body = json.loads(response.body)
    assert response.status_code == 429
    assert body["error"]["type"] == "rate_limit_exceeded"
    assert body["error"]["subnet"] == "sn1"
    assert body["error"]["retry_after"] == 12
    assert response.headers.get("retry-after") == "12"


@pytest.mark.asyncio
async def test_miner_uid_omitted_from_non_miner_errors():
    """Non-miner errors (429, 401, 500, 503) never include miner_uid."""
    for exc in [
        GatewayError("err", status_code=500),
        AuthenticationError(),
        SubnetUnavailableError(subnet="sn1"),
        RateLimitExceededError(subnet="sn1", retry_after=5),
    ]:
        response = await gateway_exception_handler(_fake_request(), exc)
        body = json.loads(response.body)
        assert "miner_uid" not in body["error"], f"miner_uid leaked in {type(exc).__name__}"


# ---------------------------------------------------------------------------
# Error envelope schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        GatewayError("err", status_code=500),
        MinerInvalidResponseError(miner_uid="abc", subnet="sn1"),
        MinerTimeoutError(miner_uid="abc", subnet="sn1"),
        SubnetUnavailableError(subnet="sn1"),
        AuthenticationError(),
        RateLimitExceededError(subnet="sn1", retry_after=5),
    ],
    ids=["500", "502", "504", "503", "401", "429"],
)
async def test_all_errors_match_envelope_schema(exc: GatewayError):
    """Every GatewayError response validates against ErrorResponse schema."""
    response = await gateway_exception_handler(_fake_request(), exc)
    body = json.loads(response.body)
    ErrorResponse.model_validate(body)


# ---------------------------------------------------------------------------
# Validation error handler (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_422_validation_error_integration(client: AsyncClient):
    """Full-stack: malformed body on unauthed endpoint returns 422 envelope.

    Uses /v1/health with POST (method not allowed) or a non-body endpoint.
    Since all subnet endpoints require auth, we test the validation handler
    directly via synthetic errors (see test_422_validation_error_via_handler).
    This test verifies the handler is *registered* by sending a request with
    an invalid JSON body shape to an endpoint that parses body first.
    """
    # POST to health endpoint with JSON body — health is GET-only, so this
    # returns 405.  Instead verify the handler registration by checking that
    # a Pydantic-invalid body to a real POST endpoint triggers 422 *before*
    # auth when the body is structurally unparseable.
    # FastAPI processes body schema before Depends() for POST endpoints,
    # so sending a completely wrong body type triggers validation first.
    response = await client.post(
        "/v1/chat/completions",
        content=b"not json at all",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer tao_sk_test_x",
        },
    )
    # FastAPI returns 422 for unparseable JSON before auth runs
    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["code"] == 422


@pytest.mark.asyncio
async def test_422_validation_error_via_handler():
    """Test validation handler directly with a synthetic RequestValidationError."""
    from pydantic import ValidationError

    from gateway.schemas.chat import ChatCompletionRequest

    try:
        ChatCompletionRequest.model_validate({"model": 123, "messages": "not_a_list"})
    except ValidationError as e:
        from fastapi.exceptions import RequestValidationError

        from gateway.middleware.error_handler import validation_exception_handler

        req_exc = RequestValidationError(e.errors())
        response = await validation_exception_handler(_fake_request(), req_exc)
        body = json.loads(response.body)

        assert response.status_code == 422
        assert body["error"]["type"] == "validation_error"
        assert body["error"]["code"] == 422
        assert isinstance(body["error"]["errors"], list)
        assert len(body["error"]["errors"]) > 0

        # Validate each field error has required keys
        for field_error in body["error"]["errors"]:
            assert "field" in field_error
            assert "message" in field_error


@pytest.mark.asyncio
async def test_422_multiple_field_errors():
    """Multiple validation errors all appear in the errors list."""
    from pydantic import ValidationError

    from gateway.schemas.chat import ChatCompletionRequest

    try:
        ChatCompletionRequest.model_validate({})
    except ValidationError as e:
        from fastapi.exceptions import RequestValidationError

        from gateway.middleware.error_handler import validation_exception_handler

        req_exc = RequestValidationError(e.errors())
        response = await validation_exception_handler(_fake_request(), req_exc)
        body = json.loads(response.body)

        assert response.status_code == 422
        # Should have errors for both 'model' and 'messages' being missing
        assert len(body["error"]["errors"]) >= 2
        fields = [e["field"] for e in body["error"]["errors"]]
        assert "model" in fields
        assert "messages" in fields


@pytest.mark.asyncio
async def test_422_field_path_dot_notation():
    """Nested field locations use dot notation (e.g., messages.0.role)."""
    from pydantic import ValidationError

    from gateway.schemas.chat import ChatCompletionRequest

    try:
        ChatCompletionRequest.model_validate({
            "model": "tao-gpt",
            "messages": [{"role": 123, "content": "hello"}],
        })
    except ValidationError as e:
        from fastapi.exceptions import RequestValidationError

        from gateway.middleware.error_handler import validation_exception_handler

        req_exc = RequestValidationError(e.errors())
        response = await validation_exception_handler(_fake_request(), req_exc)
        body = json.loads(response.body)

        assert response.status_code == 422
        fields = [e["field"] for e in body["error"]["errors"]]
        # Should have a nested path like "messages.0.role"
        assert any("messages" in f and "role" in f for f in fields)


# ---------------------------------------------------------------------------
# Catch-all exception handler (500)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catch_all_handler():
    """Unhandled exceptions return 500 with generic message, no internals."""
    from gateway.middleware.error_handler import internal_exception_handler

    exc = RuntimeError("database connection pool exhausted")
    response = await internal_exception_handler(_fake_request(), exc)
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["error"]["type"] == "internal_error"
    assert body["error"]["code"] == 500
    # Must NOT expose internal details
    assert "database" not in body["error"]["message"].lower()
    assert "pool" not in body["error"]["message"].lower()
    assert "traceback" not in json.dumps(body).lower()


@pytest.mark.asyncio
async def test_catch_all_follows_envelope():
    """Catch-all handler response validates against ErrorResponse schema."""
    from gateway.middleware.error_handler import internal_exception_handler

    exc = ValueError("unexpected value")
    response = await internal_exception_handler(_fake_request(), exc)
    body = json.loads(response.body)
    ErrorResponse.model_validate(body)


# ---------------------------------------------------------------------------
# Response metadata headers on success (AC #4)
# ---------------------------------------------------------------------------


def test_catch_all_handler_registered():
    """Verify internal_exception_handler is registered for Exception on the app.

    Registration correctness proves unhandled exceptions hit our catch-all.
    Behavioral correctness is covered by test_catch_all_handler (unit test).
    """
    from gateway.main import app as real_app
    from gateway.middleware.error_handler import internal_exception_handler

    assert Exception in real_app.exception_handlers
    assert real_app.exception_handlers[Exception] is internal_exception_handler


def test_validation_handler_registered():
    """Verify validation_exception_handler is registered for RequestValidationError."""
    from fastapi.exceptions import RequestValidationError

    from gateway.main import app as real_app
    from gateway.middleware.error_handler import validation_exception_handler

    assert RequestValidationError in real_app.exception_handlers
    assert real_app.exception_handlers[RequestValidationError] is validation_exception_handler


# ---------------------------------------------------------------------------
# Exception message sanitization (Story 3.3, Task 1.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catch_all_sanitizes_db_url_in_exception(capsys):
    """internal_exception_handler sanitizes DB URLs from exception messages before logging."""
    from gateway.middleware.error_handler import internal_exception_handler

    exc = RuntimeError(
        "Connection failed: postgresql+asyncpg://admin:s3cret_pass@db-host:5432/mydb"
    )
    await internal_exception_handler(_fake_request(), exc)
    captured = capsys.readouterr()
    assert "s3cret_pass" not in captured.out
    assert "s3cret_pass" not in captured.err


@pytest.mark.asyncio
async def test_catch_all_sanitizes_api_key_in_exception(capsys):
    """internal_exception_handler sanitizes API key patterns from exception messages."""
    from gateway.middleware.error_handler import internal_exception_handler

    exc = ValueError("Key lookup failed for tao_sk_live_abc123def456xyz789")
    await internal_exception_handler(_fake_request(), exc)
    captured = capsys.readouterr()
    assert "abc123def456xyz789" not in captured.out
    assert "abc123def456xyz789" not in captured.err


@pytest.mark.asyncio
async def test_log_sanitization_integration(client: AsyncClient, capsys):
    """Full-stack: trigger an unhandled exception path and verify log output is sanitized.

    Sends a request that goes through the full middleware stack. While we can't
    easily trigger an unhandled exception through a real endpoint, we verify that
    the structlog pipeline processes all log output through the redaction processor
    by checking that a normal request's log output contains no sensitive patterns.
    """
    # Make a real request through the full stack — triggers auth logging
    await client.post(
        "/v1/chat/completions",
        json={"model": "tao-gpt", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer tao_sk_live_abc123def456xyz789extra"},
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # The full API key must never appear in log output
    assert "abc123def456xyz789extra" not in combined
