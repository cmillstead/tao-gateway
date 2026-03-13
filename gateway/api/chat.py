from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.core.exceptions import GatewayError, MinerInvalidResponseError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from gateway.subnets.base import BaseAdapter

logger = structlog.get_logger()
router = APIRouter()


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    body: ChatCompletionRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse | StreamingResponse:
    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector

    if body.stream:
        return _handle_stream(body, request, adapter, dendrite, miner_selector)

    return await _handle_non_stream(body, adapter, dendrite, miner_selector)


def _handle_stream(
    body: ChatCompletionRequest,
    request: Request,
    adapter: BaseAdapter,
    dendrite: Any,
    miner_selector: Any,
) -> StreamingResponse:
    """Handle streaming chat completion request."""
    logger.info(
        "chat_completion_stream_request",
        model=body.model,
        message_count=len(body.messages),
    )

    # Select miner ONCE — same miner used for headers and query
    config = adapter.get_config()
    axon = miner_selector.select_miner(config.netuid)
    miner_uid = axon.hotkey[:8]

    async def _generator() -> AsyncGenerator[str, None]:
        had_error = False
        try:
            async for chunk in adapter.execute_stream(
                request_data=body.model_dump(),
                dendrite=dendrite,
                axon=axon,
                miner_uid=miner_uid,
                is_disconnected=request.is_disconnected,
            ):
                yield chunk
        except GatewayError as exc:
            had_error = True
            logger.warning(
                "chat_completion_stream_error",
                model=body.model,
                error_type=exc.error_type,
            )
        except Exception as exc:
            had_error = True
            logger.error(
                "chat_completion_stream_error",
                model=body.model,
                error_type=type(exc).__name__,
                error=str(exc),
            )

        if not had_error:
            logger.info("chat_completion_stream_complete", model=body.model)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-TaoGateway-Miner-UID": miner_uid,
            "X-TaoGateway-Subnet": config.subnet_name,
        },
    )


async def _handle_non_stream(
    body: ChatCompletionRequest,
    adapter: BaseAdapter,
    dendrite: Any,
    miner_selector: Any,
) -> JSONResponse:
    """Handle non-streaming chat completion request."""
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
