import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from gateway.core.database import get_db
from gateway.core.exceptions import GatewayError
from gateway.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from gateway.services import auth_service

logger = structlog.get_logger()
router = APIRouter()


@router.post("/signup", status_code=HTTP_201_CREATED, response_model=SignupResponse)
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)) -> SignupResponse:
    try:
        org = await auth_service.signup(request.email, request.password, db)
    except IntegrityError as exc:
        raise GatewayError(
            "Email already registered", status_code=409, error_type="conflict"
        ) from exc
    logger.info("org_created", org_id=str(org.id), email=request.email)
    return SignupResponse(id=str(org.id), email=org.email, message="Account created successfully")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    token = await auth_service.login(request.email, request.password, db)
    return LoginResponse(access_token=token)
