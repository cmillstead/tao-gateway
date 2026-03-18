import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from gateway.api.router import router
from gateway.core.bittensor import create_dendrite, create_subtensor, create_wallet
from gateway.core.config import settings
from gateway.core.database import get_engine, get_session_factory
from gateway.core.exceptions import GatewayError
from gateway.core.logging import setup_logging
from gateway.core.redis import close_redis, get_redis
from gateway.middleware.error_handler import (
    gateway_exception_handler,
    internal_exception_handler,
    validation_exception_handler,
)
from gateway.middleware.security_headers import SecurityHeadersMiddleware
from gateway.routing.metagraph_sync import MetagraphManager
from gateway.routing.scorer import MinerScorer
from gateway.routing.selector import MinerSelector
from gateway.subnets.factory import adapter_factory, get_model_names
from gateway.subnets.registry import AdapterRegistry
from gateway.tasks.debug_cleanup import DebugLogCleanupTask
from gateway.tasks.score_flush import ScoreFlushTask
from gateway.tasks.usage_aggregation import UsageAggregationTask

# Configure structlog before any logger calls — including module-level init
setup_logging()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.start_time = time.time()

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
        await redis.ping()
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

        # Register only enabled subnets (config-driven)
        adapter_registry = AdapterRegistry()
        for netuid in settings.enabled_subnets:
            adapter = adapter_factory(netuid)
            if adapter is None:
                logger.warning("unknown_subnet_skipped", netuid=netuid)
                continue
            model_names = get_model_names(netuid)
            metagraph_manager.register_subnet(netuid)
            adapter_registry.register(adapter, model_names=model_names)

        logger.info(
            "subnets_registered",
            enabled=settings.enabled_subnets,
            registered=adapter_registry.get_all_netuids(),
        )

        await metagraph_manager.start()

        try:
            for netuid in settings.enabled_subnets:
                if adapter_factory(netuid) is None:
                    continue  # Unknown subnet, already warned
                if metagraph_manager.get_metagraph(netuid) is None:
                    logger.error("startup_metagraph_empty", netuid=netuid)
                    raise RuntimeError(
                        f"Initial metagraph sync failed for SN{netuid} — "
                        "cannot route requests without metagraph data"
                    )
        except BaseException:
            await metagraph_manager.stop()
            raise

        # Build subnet timeout map for quality scoring normalization
        subnet_timeouts: dict[int, float] = {}
        for netuid in settings.enabled_subnets:
            # Look up timeout setting by convention: sn{N}_timeout_seconds
            timeout_attr = f"sn{netuid}_timeout_seconds"
            timeout_ms = getattr(settings, timeout_attr, settings.dendrite_timeout_seconds) * 1000
            subnet_timeouts[netuid] = timeout_ms

        scorer = MinerScorer(
            ema_alpha=settings.score_ema_alpha,
            subnet_timeouts=subnet_timeouts,
            sample_rate=settings.quality_sample_rate,
        )
        miner_selector = MinerSelector(
            metagraph_manager,
            scorer=scorer,
            quality_weight=settings.quality_weight,
        )

        score_flush_task = ScoreFlushTask(
            scorer=scorer,
            session_factory=get_session_factory(),
            flush_interval=settings.score_flush_interval_seconds,
            retention_days=settings.score_retention_days,
        )
        await score_flush_task.start()

        app.state.dendrite = dendrite
        app.state.metagraph_manager = metagraph_manager
        app.state.miner_selector = miner_selector
        app.state.adapter_registry = adapter_registry
        app.state.scorer = scorer
        app.state.score_flush_task = score_flush_task

        logger.info("startup_bittensor_ok")
    else:
        logger.info("startup_bittensor_skipped")
        dendrite = None
        metagraph_manager = None
        score_flush_task = None
        app.state.dendrite = None
        app.state.miner_selector = None
        app.state.adapter_registry = AdapterRegistry()
        app.state.scorer = None
        app.state.score_flush_task = None

    # Usage aggregation task (runs regardless of Bittensor)
    usage_aggregation_task = UsageAggregationTask(
        session_factory=get_session_factory(),
        aggregation_interval=settings.usage_aggregation_interval_seconds,
        retention_days=settings.usage_retention_days,
    )
    await usage_aggregation_task.start()
    app.state.usage_aggregation_task = usage_aggregation_task

    # Debug log cleanup task (runs regardless of Bittensor)
    debug_cleanup_task = DebugLogCleanupTask(
        session_factory=get_session_factory(),
        cleanup_interval_seconds=settings.debug_log_cleanup_interval_seconds,
        retention_hours=settings.debug_log_retention_hours,
    )
    await debug_cleanup_task.start()
    app.state.debug_cleanup_task = debug_cleanup_task

    yield

    # Shutdown — each step guarded so one failure doesn't skip the rest
    try:
        await debug_cleanup_task.stop()
    except Exception:
        logger.warning("shutdown_debug_cleanup_failed", exc_info=True)
    try:
        await usage_aggregation_task.stop()
    except Exception:
        logger.warning("shutdown_usage_aggregation_failed", exc_info=True)
    if score_flush_task is not None:
        try:
            await score_flush_task.stop()
        except Exception:
            logger.warning("shutdown_score_flush_failed", exc_info=True)
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
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)

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
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, internal_exception_handler)
app.include_router(router)

# Serve dashboard SPA static files (if built)
_DASHBOARD_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if _DASHBOARD_DIST.is_dir():
    # API routes are already mounted above via include_router, so they take priority.
    # Mount static assets (JS, CSS, fonts) under /assets.
    _ASSETS_DIR = _DASHBOARD_DIST / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="dashboard-assets")

    _ALLOWED_STATIC_EXT = {
        ".html", ".js", ".css", ".png", ".jpg", ".svg", ".ico",
        ".woff", ".woff2", ".ttf", ".json", ".webp", ".txt",
    }

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str) -> FileResponse:
        """Catch-all: serve index.html for SPA client-side routing."""
        file_path = _DASHBOARD_DIST / path
        if (
            file_path.is_file()
            and file_path.resolve().is_relative_to(_DASHBOARD_DIST)
            and file_path.suffix.lower() in _ALLOWED_STATIC_EXT
        ):
            return FileResponse(str(file_path))
        return FileResponse(str(_DASHBOARD_DIST / "index.html"))
