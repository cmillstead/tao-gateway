import time
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.schemas.models import ModelsListResponse, SubnetModelInfo

if TYPE_CHECKING:
    from gateway.subnets.registry import AdapterRegistry

logger = structlog.get_logger()

router = APIRouter()


@router.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    logger.info("models_list_request")

    registry: AdapterRegistry = request.app.state.adapter_registry
    metagraph_manager = getattr(request.app.state, "metagraph_manager", None)
    created = int(getattr(request.app.state, "start_time", time.time()))

    models: list[SubnetModelInfo] = []
    for info in registry.list_all():
        netuid = info.config.netuid

        # Determine status from metagraph
        status = "unavailable"
        if metagraph_manager is not None:
            mg = metagraph_manager.get_metagraph(netuid)
            if mg is not None and int(mg.n) > 0:
                status = "available"

        model_id = info.model_names[0] if info.model_names else f"tao-sn{netuid}"

        # Self-describing adapter metadata
        adapter = info.adapter
        capability = adapter.get_capability() if adapter else "Unknown"
        parameters = adapter.get_parameters() if adapter else {}

        models.append(
            SubnetModelInfo(
                id=model_id,
                created=created,
                subnet_id=netuid,
                capability=capability,
                status=status,
                parameters=parameters,
            )
        )

    response = ModelsListResponse(data=models)
    return JSONResponse(content=response.model_dump())
