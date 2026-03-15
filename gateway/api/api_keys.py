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
    ApiKeyRotateResponse,
    ApiKeyUpdateRequest,
    DebugLogEntry,
    DebugLogListResponse,
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
    api_key, full_key = await api_key_service.create_api_key(
        org_id, request.environment, db, name=request.name,
    )
    logger.info("api_key_created", org_id=str(org_id), prefix=api_key.prefix)
    return ApiKeyCreateResponse(
        id=str(api_key.id),
        key=full_key,
        prefix=api_key.prefix,
        name=api_key.name,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_revoked: bool = Query(default=False),
) -> ApiKeyListResponse:
    keys, total = await api_key_service.list_api_keys(
        org_id, db, limit=limit, offset=offset, include_revoked=include_revoked,
    )
    logger.info("api_keys_listed", org_id=str(org_id), total=total)
    return ApiKeyListResponse(
        items=[
            ApiKeyListItem(
                id=str(k.id),
                prefix=k.prefix,
                name=k.name,
                is_active=k.is_active,
                debug_mode=k.debug_mode,
                created_at=k.created_at,
            )
            for k in keys
        ],
        total=total,
    )


@router.patch("/api-keys/{key_id}", response_model=ApiKeyListItem)
async def update_api_key(
    key_id: uuid.UUID,
    body: ApiKeyUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyListItem:
    try:
        redis = await get_redis()
    except Exception:
        redis = None
    key = await api_key_service.update_api_key(
        key_id, org_id, db, redis, debug_mode=body.debug_mode,
    )
    if key is None:
        raise GatewayError("API key not found", status_code=404, error_type="not_found")
    logger.info(
        "api_key_updated",
        org_id=str(org_id),
        key_id=str(key_id),
        debug_mode=key.debug_mode,
    )
    return ApiKeyListItem(
        id=str(key.id),
        prefix=key.prefix,
        name=key.name,
        is_active=key.is_active,
        debug_mode=key.debug_mode,
        created_at=key.created_at,
    )


@router.get("/api-keys/{key_id}/debug-logs", response_model=DebugLogListResponse)
async def get_debug_logs(
    key_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DebugLogListResponse:
    logs, total = await api_key_service.get_debug_logs(
        key_id, org_id, db, limit=limit, offset=offset,
    )
    return DebugLogListResponse(
        items=[
            DebugLogEntry(
                id=str(log.id),
                usage_record_id=str(log.usage_record_id),
                request_body=log.request_body,
                response_body=log.response_body,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
    )


@router.post(
    "/api-keys/rotate/{key_id}",
    status_code=HTTP_201_CREATED,
    response_model=ApiKeyRotateResponse,
)
async def rotate_api_key(
    key_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRotateResponse:
    try:
        redis = await get_redis()
    except Exception:
        redis = None
    new_key, full_key, old_key = await api_key_service.rotate_api_key(
        key_id, org_id, db, redis,
    )
    logger.info(
        "api_key_rotated",
        org_id=str(org_id),
        old_key_id=str(key_id),
        new_prefix=new_key.prefix,
    )
    return ApiKeyRotateResponse(
        new_key=ApiKeyCreateResponse(
            id=str(new_key.id),
            key=full_key,
            prefix=new_key.prefix,
            name=new_key.name,
            created_at=new_key.created_at,
        ),
        revoked_key_id=str(old_key.id),
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
