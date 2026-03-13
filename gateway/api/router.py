from fastapi import APIRouter

from gateway.api.api_keys import router as api_keys_router
from gateway.api.auth import router as auth_router
from gateway.api.health import router as health_router

router = APIRouter()
router.include_router(health_router, tags=["Health"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(api_keys_router, prefix="/dashboard", tags=["API Keys"])
