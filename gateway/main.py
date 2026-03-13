from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gateway.api.router import router
from gateway.core.config import settings
from gateway.core.database import engine
from gateway.core.exceptions import GatewayError
from gateway.core.logging import setup_logging
from gateway.core.redis import close_redis
from gateway.middleware.error_handler import gateway_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="TaoGateway",
    description="REST API gateway for the Bittensor decentralized AI network",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_exception_handler(GatewayError, gateway_exception_handler)  # type: ignore[arg-type]
app.include_router(router)
