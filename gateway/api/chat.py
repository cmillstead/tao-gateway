import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from gateway.core.exceptions import GatewayError, MinerInvalidResponseError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

logger = structlog.get_logger()
router = APIRouter()


@router.post("/chat/completions")
async def create_chat_completion(
    body: ChatCompletionRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse:
    if body.stream:
        return JSONResponse(
            status_code=501,
            content={
                "error": {
                    "type": "not_implemented",
                    "message": "Streaming not yet supported. Use stream=false.",
                    "code": 501,
                }
            },
        )

    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector

    logger.info(
        "chat_completion_request",
        model=body.model,
        message_count=len(body.messages),
    )

    try:
        response_data, headers = await adapter.execute(
            request_data=body.model_dump(),
            dendrite=dendrite,
            miner_selector=miner_selector,
        )
    except GatewayError as exc:
        logger.warning(
            "chat_completion_error",
            model=body.model,
            error_type=exc.error_type,
            status_code=exc.status_code,
        )
        raise
    except Exception as exc:
        logger.error(
            "chat_completion_error",
            model=body.model,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    # Validate response against OpenAI schema before returning
    try:
        ChatCompletionResponse.model_validate(response_data)
    except Exception as exc:
        logger.error(
            "chat_completion_response_invalid",
            model=body.model,
            error=str(exc),
        )
        raise MinerInvalidResponseError(
            miner_uid=headers.get("X-TaoGateway-Miner-UID", "unknown"),
            subnet=headers.get("X-TaoGateway-Subnet", "unknown"),
        ) from exc

    logger.info(
        "chat_completion_success",
        model=body.model,
        miner_uid=headers.get("X-TaoGateway-Miner-UID"),
        latency_ms=headers.get("X-TaoGateway-Latency-Ms"),
    )

    return JSONResponse(content=response_data, headers=headers)
