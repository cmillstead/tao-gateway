import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.database import get_db
from gateway.middleware.auth import get_current_org_id
from gateway.schemas.api_keys import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyListItem
from gateway.services import api_key_service

logger = structlog.get_logger()
router = APIRouter()


@router.post("/api-keys", status_code=HTTP_201_CREATED, response_model=ApiKeyCreateResponse)
async def create_api_key(
    request: ApiKeyCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreateResponse:
    api_key, full_key = await api_key_service.create_api_key(org_id, request.environment, db)
    logger.info("api_key_created", org_id=str(org_id), prefix=api_key.prefix)
    return ApiKeyCreateResponse(
        id=str(api_key.id),
        key=full_key,
        prefix=api_key.prefix,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyListItem])
async def list_api_keys(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyListItem]:
    keys = await api_key_service.list_api_keys(org_id, db)
    return [
        ApiKeyListItem(
            id=str(k.id),
            prefix=k.prefix,
            is_active=k.is_active,
            created_at=k.created_at,
        )
        for k in keys
    ]
