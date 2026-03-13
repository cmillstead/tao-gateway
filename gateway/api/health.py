from fastapi import APIRouter

from gateway.core.config import settings
from gateway.schemas.health import HealthResponse

router = APIRouter()


@router.get("/v1/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version=settings.app_version)
