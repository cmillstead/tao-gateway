"""AI content detection endpoint (SN32)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Request

from gateway.api._subnet_handler import execute_subnet_request
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.middleware.rate_limit import enforce_rate_limit
from gateway.schemas.detection import DetectionRequest, DetectionResponse

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post("/moderations", response_model=None)
async def create_moderation(
    body: DetectionRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse:
    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    config = adapter.get_config()
    rate_result = await enforce_rate_limit(str(api_key.key_id), config.netuid, config.subnet_name)
    request.state.rate_limit_result = rate_result

    scorer = getattr(request.app.state, "scorer", None)

    return await execute_subnet_request(
        adapter=adapter,
        request_data=body.model_dump(),
        request_body_json=body.model_dump_json(),
        response_schema=DetectionResponse,
        api_key=api_key,
        rate_result=rate_result,
        endpoint="/v1/moderations",
        log_event="detection",
        dendrite=request.app.state.dendrite,
        miner_selector=request.app.state.miner_selector,
        scorer=scorer,
        extra_log={"text_count": len(body.input)},
    )
