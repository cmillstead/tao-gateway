from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sqlalchemy import text

from gateway.api.router import router
from gateway.core.config import settings
from gateway.core.database import get_engine
from gateway.core.exceptions import GatewayError
from gateway.core.logging import setup_logging
from gateway.core.redis import close_redis, get_redis
from gateway.middleware.error_handler import gateway_exception_handler

# Configure structlog before any logger calls — including module-level init
setup_logging()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: verify DB and Redis connectivity before accepting traffic
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("startup_db_ok")
    except Exception:
        logger.error("startup_db_failed")
        raise

    try:
        redis = await get_redis()
        await redis.ping()  # type: ignore[misc]
        logger.info("startup_redis_ok")
    except Exception:
        logger.error("startup_redis_failed")
        raise

    yield

    # Shutdown
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
