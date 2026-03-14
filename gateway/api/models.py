import time
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.schemas.models import ModelsListResponse, SubnetModelInfo

if TYPE_CHECKING:
    from gateway.subnets.registry import AdapterRegistry

logger = structlog.get_logger()

router = APIRouter()

_CAPABILITY_MAP: dict[str, str] = {
    "sn1": "Text Generation",
    "sn19": "Image Generation",
    "sn62": "Code Generation",
}

_PARAMETER_MAP: dict[str, dict[str, Any]] = {
    "sn1": {
        "model": "string (required)",
        "messages": "array (required)",
        "max_tokens": "integer (optional)",
        "temperature": "number (optional, 0-2)",
        "stream": "boolean (optional)",
    },
    "sn19": {
        "prompt": "string (required, max 2000 chars)",
        "model": "string (required)",
        "resolution": "string (optional, e.g. '1024x1024')",
        "style": "string (optional)",
    },
    "sn62": {
        "prompt": "string (required, max 16000 chars)",
        "model": "string (required)",
        "language": "string (required, max 32 chars)",
        "context": "string (optional, max 32000 chars)",
    },
}

@router.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    logger.info("models_list_request")

    registry: AdapterRegistry = request.app.state.adapter_registry
    metagraph_manager = getattr(request.app.state, "metagraph_manager", None)
    created = int(getattr(request.app.state, "start_time", time.time()))

    models: list[SubnetModelInfo] = []
    for info in registry.list_all():
        subnet_name = info.config.subnet_name
        netuid = info.config.netuid

        # Determine status from metagraph
        status = "unavailable"
        if metagraph_manager is not None:
            mg = metagraph_manager.get_metagraph(netuid)
            if mg is not None and int(mg.n) > 0:
                status = "available"

        model_id = info.model_names[0] if info.model_names else f"tao-sn{netuid}"

        models.append(
            SubnetModelInfo(
                id=model_id,
                created=created,
                subnet_id=netuid,
                capability=_CAPABILITY_MAP.get(subnet_name, "Unknown"),
                status=status,
                parameters=_PARAMETER_MAP.get(subnet_name, {}),
            )
        )

    response = ModelsListResponse(data=models)
    return JSONResponse(content=response.model_dump())
