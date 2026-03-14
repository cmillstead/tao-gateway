from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from gateway.subnets.registry import AdapterRegistry
from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter

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

    # Bittensor SDK initialization (optional — disable for local dev without wallet)
    if settings.enable_bittensor:
        try:
            wallet = create_wallet()
            subtensor = create_subtensor()
            dendrite = create_dendrite(wallet)
        except Exception as exc:
            logger.error("startup_bittensor_failed", error=str(exc), error_type=type(exc).__name__)
            raise

        metagraph_manager = MetagraphManager(
            subtensor=subtensor,
            sync_interval=settings.metagraph_sync_interval_seconds,
            sync_timeout=settings.dendrite_timeout_seconds,
        )
        metagraph_manager.register_subnet(settings.sn1_netuid)
        metagraph_manager.register_subnet(settings.sn19_netuid)
        await metagraph_manager.start()

        try:
            if metagraph_manager.get_metagraph(settings.sn1_netuid) is None:
                logger.error(
                    "startup_metagraph_empty",
                    netuid=settings.sn1_netuid,
                )
                raise RuntimeError(
                    f"Initial metagraph sync failed for SN{settings.sn1_netuid} — "
                    "cannot route requests without metagraph data"
                )
            if metagraph_manager.get_metagraph(settings.sn19_netuid) is None:
                logger.error(
                    "startup_metagraph_empty",
                    netuid=settings.sn19_netuid,
                )
                raise RuntimeError(
                    f"Initial metagraph sync failed for SN{settings.sn19_netuid} — "
                    "cannot route requests without metagraph data"
                )
        except BaseException:
            await metagraph_manager.stop()
            raise

        miner_selector = MinerSelector(metagraph_manager)

        adapter_registry = AdapterRegistry()
        adapter_registry.register(SN1TextAdapter(), model_names=["tao-sn1"])
        adapter_registry.register(SN19ImageAdapter(), model_names=["tao-sn19"])

        app.state.dendrite = dendrite
        app.state.metagraph_manager = metagraph_manager
        app.state.miner_selector = miner_selector
        app.state.adapter_registry = adapter_registry

        logger.info("startup_bittensor_ok")
    else:
        logger.info("startup_bittensor_skipped")
        dendrite = None
        metagraph_manager = None
        app.state.dendrite = None
        app.state.miner_selector = None
        app.state.adapter_registry = AdapterRegistry()

    yield

    # Shutdown — each step guarded so one failure doesn't skip the rest
    if metagraph_manager is not None:
        try:
            await metagraph_manager.stop()
        except Exception:
            logger.warning("shutdown_metagraph_manager_failed", exc_info=True)
    if dendrite is not None:
        try:
            await dendrite.aclose_session()
        except Exception:
            logger.warning("shutdown_dendrite_close_failed", exc_info=True)
    try:
        await engine.dispose()
    except Exception:
        logger.warning("shutdown_engine_dispose_failed", exc_info=True)
    try:
        await close_redis()
    except Exception:
        logger.warning("shutdown_redis_close_failed", exc_info=True)


app = FastAPI(
    title="TaoGateway",
    description="REST API gateway for the Bittensor decentralized AI network",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_MAX_BODY_SIZE = 1_000_000  # 1 MB


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Reject requests whose body exceeds the maximum size.

    Checks Content-Length up front when available, and also wraps the
    ASGI receive callable to enforce the limit during body consumption
    (handles chunked transfer-encoding where Content-Length is absent).
    """
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except (ValueError, OverflowError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "request_too_large",
                        "message": "Invalid Content-Length",
                    }
                },
            )
        if size < 0:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_request",
                        "message": "Invalid Content-Length",
                    }
                },
            )
        if size > _MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "type": "request_too_large",
                        "message": f"Request body too large. Max size is {_MAX_BODY_SIZE} bytes.",
                    }
                },
            )

    # Wrap receive to track bytes read and enforce limit on chunked bodies
    bytes_received = 0
    original_receive = request._receive
    body_too_large = False

    async def _limited_receive() -> dict[str, Any]:
        nonlocal bytes_received, body_too_large
        message = await original_receive()
        if message.get("type") == "http.request":
            body = message.get("body", b"")
            bytes_received += len(body)
            if bytes_received > _MAX_BODY_SIZE:
                body_too_large = True
                return {"type": "http.request", "body": b"", "more_body": False}
        return message  # type: ignore[return-value]

    request._receive = _limited_receive
    response = await call_next(request)

    if body_too_large:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "type": "request_too_large",
                    "message": f"Request body too large. Max size is {_MAX_BODY_SIZE} bytes.",
                }
            },
        )

    return response


app.add_exception_handler(GatewayError, gateway_exception_handler)  # type: ignore[arg-type]
app.include_router(router)
