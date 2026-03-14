from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError, MinerInvalidResponseError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.middleware.rate_limit import enforce_rate_limit
from gateway.schemas.images import ImageGenerationRequest, ImageGenerationResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post("/images/generate", response_model=None)
async def generate_image(
    body: ImageGenerationRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse:
    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    config = adapter.get_config()
    rate_result = await enforce_rate_limit(str(api_key.key_id), config.netuid, config.subnet_name)
    request.state.rate_limit_result = rate_result
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector
    scorer = getattr(request.app.state, "scorer", None)

    logger.info(
        "image_generation_request",
        model=body.model,
        size=body.size,
    )

    try:
        response_data, headers = await adapter.execute(
            request_data=body.model_dump(),
            dendrite=dendrite,
            miner_selector=miner_selector,
            scorer=scorer,
        )
    except GatewayError as exc:
        logger.warning(
            "image_generation_error",
            model=body.model,
            error_type=exc.error_type,
            status_code=exc.status_code,
        )
        raise
    except Exception as exc:
        logger.error(
            "image_generation_error",
            model=body.model,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    # Validate response against schema before returning
    try:
        ImageGenerationResponse.model_validate(response_data)
    except Exception as exc:
        logger.error(
            "image_generation_response_invalid",
            model=body.model,
            error=str(exc),
        )
        raise MinerInvalidResponseError(
            miner_uid=headers.get("X-TaoGateway-Miner-UID", "unknown"),
            subnet=headers.get("X-TaoGateway-Subnet", "unknown"),
        ) from exc

    logger.info(
        "image_generation_success",
        model=body.model,
        miner_uid=headers.get("X-TaoGateway-Miner-UID"),
        latency_ms=headers.get("X-TaoGateway-Latency-Ms"),
    )

    return JSONResponse(content=response_data, headers={**headers, **rate_result.to_headers()})
