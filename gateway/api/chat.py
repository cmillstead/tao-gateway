from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.core.config import settings
from gateway.core.exceptions import GatewayError, MinerInvalidResponseError, RateLimitExceededError
from gateway.core.rate_limit import check_rate_limit
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from gateway.subnets.base import SSE_DONE

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import bittensor as bt

    from gateway.routing.selector import MinerSelector
    from gateway.subnets.base import BaseAdapter

logger = structlog.get_logger()


async def _rate_limit_chat(api_key: ApiKeyInfo) -> None:
    """Per-API-key rate limit on chat endpoint.

    Falls back to an in-memory rate limiter when Redis is unavailable.
    """
    key = f"chat_rate:{api_key.key_id}"
    result = await check_rate_limit(
        key=key,
        limit=settings.chat_rate_limit_per_minute,
        window_seconds=60,
        fallback_limit=settings.chat_rate_limit_per_minute,
        log_prefix="chat_rate_limit",
    )
    if result == -1:
        raise RateLimitExceededError("Chat rate limit exceeded. Try again later.")
    if result is not None and result > settings.chat_rate_limit_per_minute:
        raise RateLimitExceededError("Chat rate limit exceeded. Try again later.")


router = APIRouter()


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    body: ChatCompletionRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse | StreamingResponse:
    await _rate_limit_chat(api_key)
    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector

    if body.stream:
        return await _handle_stream(body, request, adapter, dendrite, miner_selector)

    return await _handle_non_stream(body, adapter, dendrite, miner_selector)


async def _handle_stream(
    body: ChatCompletionRequest,
    request: Request,
    adapter: BaseAdapter,
    dendrite: bt.Dendrite,
    miner_selector: MinerSelector,
) -> StreamingResponse:
    """Handle streaming chat completion request."""
    logger.info(
        "chat_completion_stream_request",
        model=body.model,
        message_count=len(body.messages),
    )

    headers, stream = await adapter.execute_stream(
        request_data=body.model_dump(),
        dendrite=dendrite,
        miner_selector=miner_selector,
        is_disconnected=request.is_disconnected,
    )
    miner_uid = headers["X-TaoGateway-Miner-UID"]

    async def _generator() -> AsyncGenerator[str, None]:
        had_error = False
        try:
            async for chunk in stream:
                yield chunk
        except GatewayError as exc:
            had_error = True
            logger.warning(
                "chat_completion_stream_error",
                model=body.model,
                error_type=exc.error_type,
            )
            yield adapter.sse_error(exc.error_type, exc.message, miner_uid)
            yield SSE_DONE
        except Exception as exc:
            had_error = True
            logger.error(
                "chat_completion_stream_error",
                model=body.model,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            yield adapter.sse_error("internal_error", "Internal server error", miner_uid)
            yield SSE_DONE

        if not had_error:
            logger.info("chat_completion_stream_complete", model=body.model)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            **headers,
        },
    )


async def _handle_non_stream(
    body: ChatCompletionRequest,
    adapter: BaseAdapter,
    dendrite: bt.Dendrite,
    miner_selector: MinerSelector,
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
