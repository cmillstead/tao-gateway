"""Shared handler for non-streaming subnet endpoint requests.

Extracts the common execute -> validate -> record_usage -> respond pattern
used by chat (non-stream), images, and code endpoints.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from fastapi.responses import JSONResponse

from gateway.core.constants import HDR_LATENCY_MS, HDR_MINER_UID, HDR_SUBNET
from gateway.core.database import get_session_factory
from gateway.core.exceptions import GatewayError, MinerInvalidResponseError
from gateway.middleware.usage import record_usage, safe_json_dumps

if TYPE_CHECKING:
    from pydantic import BaseModel

    from gateway.middleware.auth import ApiKeyInfo
    from gateway.middleware.rate_limit import RateLimitResult
    from gateway.subnets.base import BaseAdapter

logger = structlog.get_logger()


async def execute_subnet_request(
    *,
    adapter: BaseAdapter,
    request_data: dict[str, Any],
    request_body_json: str,
    response_schema: type[BaseModel],
    api_key: ApiKeyInfo,
    rate_result: RateLimitResult,
    endpoint: str,
    log_event: str,
    dendrite: Any,
    miner_selector: Any,
    scorer: Any = None,
    extra_log: dict[str, Any] | None = None,
) -> JSONResponse:
    """Execute a subnet adapter request with usage recording and response validation."""
    config = adapter.get_config()
    log_fields = {"model": request_data.get("model"), **(extra_log or {})}
    logger.info(f"{log_event}_request", **log_fields)

    try:
        response_data, headers = await adapter.execute(
            request_data=request_data,
            dendrite=dendrite,
            miner_selector=miner_selector,
            scorer=scorer,
        )
    except GatewayError as exc:
        logger.warning(f"{log_event}_error", error_type=exc.error_type, **log_fields)
        asyncio.create_task(record_usage(
            session_factory=get_session_factory(),
            api_key_id=api_key.key_id,
            org_id=api_key.org_id,
            subnet_name=config.subnet_name,
            netuid=config.netuid,
            endpoint=endpoint,
            miner_uid=None,
            latency_ms=0,
            status_code=exc.status_code,
            debug_mode=api_key.debug_mode,
            request_body=request_body_json if api_key.debug_mode else None,
        ))
        raise
    except Exception as exc:
        logger.error(
            f"{log_event}_error",
            error_type=type(exc).__name__,
            error=str(exc),
            **log_fields,
        )
        asyncio.create_task(record_usage(
            session_factory=get_session_factory(),
            api_key_id=api_key.key_id,
            org_id=api_key.org_id,
            subnet_name=config.subnet_name,
            netuid=config.netuid,
            endpoint=endpoint,
            miner_uid=None,
            latency_ms=0,
            status_code=500,
            debug_mode=api_key.debug_mode,
            request_body=request_body_json if api_key.debug_mode else None,
        ))
        raise

    try:
        response_schema.model_validate(response_data)
    except Exception as exc:
        logger.error(f"{log_event}_response_invalid", error=str(exc), **log_fields)
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
        endpoint=endpoint,
        miner_uid=headers.get(HDR_MINER_UID),
        latency_ms=int(headers.get(HDR_LATENCY_MS, 0)),
        status_code=200,
        debug_mode=api_key.debug_mode,
        request_body=request_body_json if api_key.debug_mode else None,
        response_body=safe_json_dumps(response_data) if api_key.debug_mode else None,
    ))

    logger.info(
        f"{log_event}_success",
        miner_uid=headers.get(HDR_MINER_UID),
        latency_ms=headers.get(HDR_LATENCY_MS),
        **log_fields,
    )

    return JSONResponse(content=response_data, headers={**headers, **rate_result.to_headers()})
