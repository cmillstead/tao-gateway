from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from gateway.core.constants import HDR_LATENCY_MS, HDR_MINER_UID, HDR_SUBNET
from gateway.core.database import get_session_factory
from gateway.core.exceptions import GatewayError, MinerInvalidResponseError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.middleware.rate_limit import enforce_rate_limit
from gateway.middleware.usage import record_usage
from gateway.schemas.code import CodeCompletionRequest, CodeCompletionResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post("/code/completions", response_model=None)
async def generate_code(
    body: CodeCompletionRequest,
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
        "code_completion_request",
        model=body.model,
        language=body.language,
    )

    config = adapter.get_config()

    try:
        response_data, headers = await adapter.execute(
            request_data=body.model_dump(),
            dendrite=dendrite,
            miner_selector=miner_selector,
            scorer=scorer,
        )
    except GatewayError as exc:
        logger.warning(
            "code_completion_error",
            model=body.model,
            error_type=exc.error_type,
            status_code=exc.status_code,
        )
        asyncio.create_task(record_usage(
            session_factory=get_session_factory(),
            api_key_id=api_key.key_id,
            org_id=api_key.org_id,
            subnet_name=config.subnet_name,
            netuid=config.netuid,
            endpoint="/v1/code/completions",
            miner_uid=None,
            latency_ms=0,
            status_code=exc.status_code,
        ))
        raise
    except Exception as exc:
        logger.error(
            "code_completion_error",
            model=body.model,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    # Validate response against schema before returning
    try:
        CodeCompletionResponse.model_validate(response_data)
    except Exception as exc:
        logger.error(
            "code_completion_response_invalid",
            model=body.model,
            error=str(exc),
        )
        raise MinerInvalidResponseError(
            miner_uid=headers.get(HDR_MINER_UID, "unknown"),
            subnet=headers.get(HDR_SUBNET, "unknown"),
        ) from exc

    asyncio.create_task(record_usage(
        session_factory=get_session_factory(),
        api_key_id=api_key.key_id,
        org_id=api_key.org_id,
        subnet_name=config.subnet_name,
        netuid=config.netuid,
        endpoint="/v1/code/completions",
        miner_uid=headers.get(HDR_MINER_UID),
        latency_ms=int(headers.get(HDR_LATENCY_MS, 0)),
        status_code=200,
    ))

    logger.info(
        "code_completion_success",
        model=body.model,
        miner_uid=headers.get(HDR_MINER_UID),
        latency_ms=headers.get(HDR_LATENCY_MS),
    )

    return JSONResponse(content=response_data, headers={**headers, **rate_result.to_headers()})
