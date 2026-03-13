import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.database import get_db
from gateway.core.exceptions import GatewayError
from gateway.core.redis import get_redis
from gateway.middleware.auth import get_current_org_id
from gateway.schemas.api_keys import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
)
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


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApiKeyListResponse:
    keys, total = await api_key_service.list_api_keys(org_id, db, limit=limit, offset=offset)
    return ApiKeyListResponse(
        items=[
            ApiKeyListItem(
                id=str(k.id),
                prefix=k.prefix,
                is_active=k.is_active,
                created_at=k.created_at,
            )
            for k in keys
        ],
        total=total,
    )


@router.delete("/api-keys/{key_id}", status_code=200, response_model=ApiKeyRevokeResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRevokeResponse:
    try:
        redis = await get_redis()
    except Exception:
        redis = None
    key = await api_key_service.revoke_api_key(key_id, org_id, db, redis)
    if key is None:
        raise GatewayError("API key not found", status_code=404, error_type="not_found")
    logger.info("api_key_revoked", org_id=str(org_id), key_id=str(key_id))
    return ApiKeyRevokeResponse(message="API key revoked")
