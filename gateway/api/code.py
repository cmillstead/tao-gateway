from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from gateway.api._subnet_handler import execute_subnet_request
from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.middleware.rate_limit import enforce_rate_limit
from gateway.schemas.code import CodeCompletionRequest, CodeCompletionResponse

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

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

    return await execute_subnet_request(
        adapter=adapter,
        request_data=body.model_dump(),
        request_body_json=body.model_dump_json(),
        response_schema=CodeCompletionResponse,
        api_key=api_key,
        rate_result=rate_result,
        endpoint="/v1/code/completions",
        log_event="code_completion",
        dendrite=request.app.state.dendrite,
        miner_selector=request.app.state.miner_selector,
        scorer=getattr(request.app.state, "scorer", None),
        extra_log={"language": body.language},
    )
