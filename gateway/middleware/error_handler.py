import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError

logger = structlog.get_logger()


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
    # miner_uid intentionally omitted from client-facing responses (SEC-018)
    miner_uid = getattr(exc, "miner_uid", None)
    if miner_uid is not None:
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
