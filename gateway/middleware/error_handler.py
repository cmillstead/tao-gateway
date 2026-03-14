import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError
from gateway.core.logging import redact_string_value

logger = structlog.get_logger()

# Status codes where miner_uid is included in the client-facing error body.
# These are upstream miner failures (502/504) where the hotkey prefix helps
# developers debug which miner malfunctioned.  All other error types omit
# miner_uid from the response (SEC-018 scoped exception for Story 3.2).
_MINER_ERROR_CODES = {502, 504}


async def gateway_exception_handler(request: Request, exc: GatewayError) -> JSONResponse:
    body: dict[str, object] = {
        "type": exc.error_type,
        "message": exc.message,
        "code": exc.status_code,
    }
    reason = getattr(exc, "reason", None)
    if reason is not None:
        body["reason"] = reason
    subnet = getattr(exc, "subnet", None)
    if subnet is not None:
        body["subnet"] = subnet
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None and retry_after > 0:
        body["retry_after"] = retry_after

    miner_uid = getattr(exc, "miner_uid", None)
    if miner_uid is not None:
        # Include miner_uid in 502/504 responses (safe 8-char hotkey prefix).
        # Omit from all other error types (SEC-018).
        if exc.status_code in _MINER_ERROR_CODES:
            body["miner_uid"] = miner_uid
        logger.warning(
            "gateway_error",
            miner_uid=miner_uid,
            error_type=exc.error_type,
            subnet=subnet,
        )

    headers: dict[str, str] = {}
    if retry_after is not None and retry_after > 0:
        headers["Retry-After"] = str(retry_after)
    # Include rate limit headers from request state if available (set by
    # endpoint rate limit checks before the handler raised this error).
    rate_result = getattr(request.state, "rate_limit_result", None)
    if rate_result is not None:
        headers.update(rate_result.to_headers())
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": body},
        headers=headers or None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Transform Pydantic validation errors into the standard error envelope."""
    field_errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        # Strip leading segment that indicates parameter source (body/query/path)
        parts = [str(p) for p in loc if p not in ("body", "query", "path")]
        field = ".".join(parts) if parts else "unknown"
        field_errors.append({
            "field": field,
            "message": error.get("msg", "Validation error"),
            "value": error.get("input"),
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "code": 422,
                "errors": field_errors,
            }
        },
    )


async def internal_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — generic 500, no internal details."""
    logger.error(
        "unhandled_exception",
        error_type=type(exc).__name__,
        error=redact_string_value(str(exc)),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "An internal error occurred",
                "code": 500,
            }
        },
    )
