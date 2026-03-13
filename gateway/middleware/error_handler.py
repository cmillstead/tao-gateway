from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError


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
    miner_uid = getattr(exc, "miner_uid", None)
    if miner_uid is not None:
        body["miner_uid"] = miner_uid
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": body},
    )
