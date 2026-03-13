from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sqlalchemy import text

from gateway.api.router import router
from gateway.core.bittensor import create_dendrite, create_subtensor, create_wallet
from gateway.core.config import settings
from gateway.core.database import get_engine
from gateway.core.exceptions import GatewayError
from gateway.core.logging import setup_logging
from gateway.core.redis import close_redis, get_redis
from gateway.middleware.error_handler import gateway_exception_handler
from gateway.routing.metagraph_sync import MetagraphManager
from gateway.routing.selector import MinerSelector

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

    # Bittensor SDK initialization
    try:
        wallet = create_wallet()
        subtensor = create_subtensor()
        dendrite = create_dendrite(wallet)
    except Exception:
        logger.error("startup_bittensor_failed")
        raise

    metagraph_manager = MetagraphManager(
        subtensor=subtensor,
        sync_interval=settings.metagraph_sync_interval_seconds,
    )
    metagraph_manager.register_subnet(settings.sn1_netuid)
    await metagraph_manager.start()

    if metagraph_manager.get_metagraph(settings.sn1_netuid) is None:
        logger.error(
            "startup_metagraph_empty",
            netuid=settings.sn1_netuid,
        )
        raise RuntimeError(
            f"Initial metagraph sync failed for SN{settings.sn1_netuid} — "
            "cannot route requests without metagraph data"
        )

    miner_selector = MinerSelector(metagraph_manager)

    app.state.dendrite = dendrite
    app.state.metagraph_manager = metagraph_manager
    app.state.miner_selector = miner_selector

    logger.info("startup_bittensor_ok")

    yield

    # Shutdown
    await metagraph_manager.stop()
    await dendrite.aclose_session()
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
