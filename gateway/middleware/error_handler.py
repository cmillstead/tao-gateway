from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError


async def gateway_exception_handler(request: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.error_type,
                "message": exc.message,
                "code": exc.status_code,
            }
        },
    )
