from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.api._subnet_handler import execute_subnet_request
from gateway.core.constants import HDR_MINER_UID
from gateway.core.database import get_session_factory
from gateway.core.exceptions import GatewayError
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.middleware.rate_limit import RateLimitResult, enforce_rate_limit
from gateway.middleware.usage import record_usage
from gateway.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from gateway.subnets.base import SSE_DONE

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import bittensor as bt

    from gateway.routing.selector import MinerSelector
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
    config = adapter.get_config()
    rate_result = await enforce_rate_limit(str(api_key.key_id), config.netuid, config.subnet_name)
    request.state.rate_limit_result = rate_result
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector

    scorer = getattr(request.app.state, "scorer", None)

    if body.stream:
        return await _handle_stream(
            body, request, adapter, dendrite, miner_selector, rate_result, scorer, api_key,
        )

    return await _handle_non_stream(
        body, adapter, dendrite, miner_selector, rate_result, scorer, api_key,
    )


async def _handle_stream(
    body: ChatCompletionRequest,
    request: Request,
    adapter: BaseAdapter,
    dendrite: bt.Dendrite,
    miner_selector: MinerSelector,
    rate_result: RateLimitResult,
    scorer: Any = None,
    api_key: ApiKeyInfo | None = None,
) -> StreamingResponse:
    """Handle streaming chat completion request."""
    logger.info(
        "chat_completion_stream_request",
        model=body.model,
        message_count=len(body.messages),
    )

    config = adapter.get_config()

    headers, stream = await adapter.execute_stream(
        request_data=body.model_dump(),
        dendrite=dendrite,
        miner_selector=miner_selector,
        is_disconnected=request.is_disconnected,
        scorer=scorer,
    )
    miner_uid = headers[HDR_MINER_UID]

    stream_start = time.monotonic()

    # Capture request body for debug logging before streaming starts
    debug_request_body = body.model_dump_json() if (api_key and api_key.debug_mode) else None

    async def _generator() -> AsyncGenerator[str, None]:
        had_error = False
        collected_chunks: list[str] | None = [] if (api_key and api_key.debug_mode) else None
        try:
            async for chunk in stream:
                if collected_chunks is not None:
                    collected_chunks.append(chunk)
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
        finally:
            elapsed_ms = round((time.monotonic() - stream_start) * 1000)
            if api_key is not None:
                debug_response = (
                    "".join(collected_chunks)
                    if (api_key.debug_mode and collected_chunks)
                    else None
                )
                asyncio.create_task(record_usage(
                    session_factory=get_session_factory(),
                    api_key_id=api_key.key_id,
                    org_id=api_key.org_id,
                    subnet_name=config.subnet_name,
                    netuid=config.netuid,
                    endpoint="/v1/chat/completions",
                    miner_uid=miner_uid,
                    latency_ms=elapsed_ms,
                    status_code=200 if not had_error else 502,
                    debug_mode=api_key.debug_mode,
                    request_body=debug_request_body,
                    response_body=debug_response,
                ))

        if not had_error:
            logger.info("chat_completion_stream_complete", model=body.model)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            **headers,
            **rate_result.to_headers(),
        },
    )


async def _handle_non_stream(
    body: ChatCompletionRequest,
    adapter: BaseAdapter,
    dendrite: bt.Dendrite,
    miner_selector: MinerSelector,
    rate_result: RateLimitResult,
    scorer: Any = None,
    api_key: ApiKeyInfo | None = None,
) -> JSONResponse:
    """Handle non-streaming chat completion request."""
    if api_key is None:
        msg = "API key required"
        raise ValueError(msg)

    return await execute_subnet_request(
        adapter=adapter,
        request_data=body.model_dump(),
        request_body_json=body.model_dump_json(),
        response_schema=ChatCompletionResponse,
        api_key=api_key,
        rate_result=rate_result,
        endpoint="/v1/chat/completions",
        log_event="chat_completion",
        dendrite=dendrite,
        miner_selector=miner_selector,
        scorer=scorer,
        extra_log={"message_count": len(body.messages)},
    )
