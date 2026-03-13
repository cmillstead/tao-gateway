import os
from unittest.mock import MagicMock, patch

# Hard-override to prevent tests ever running against production.
# These MUST be set before any gateway imports.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway_test"
os.environ["DEBUG"] = "true"

_db_url = os.environ["DATABASE_URL"]
assert "test" in _db_url, f"Refusing to run tests against non-test database: {_db_url}"

# Mock Bittensor SDK before gateway imports — prevents real wallet/network access
_mock_bt_wallet = MagicMock()
_mock_bt_subtensor = MagicMock()
_mock_bt_dendrite = MagicMock()
# Make metagraph sync succeed with a minimal fake metagraph
_mock_metagraph = MagicMock()
_mock_metagraph.n = 0
_mock_bt_subtensor.metagraph.return_value = _mock_metagraph

_bt_patches = [
    patch("gateway.core.bittensor.bt.Wallet", return_value=_mock_bt_wallet),
    patch("gateway.core.bittensor.bt.Subtensor", return_value=_mock_bt_subtensor),
    patch("gateway.core.bittensor.bt.Dendrite", return_value=_mock_bt_dendrite),
]
for p in _bt_patches:
    p.start()

import atexit as _atexit  # noqa: E402


def _stop_bt_patches() -> None:
    for p in _bt_patches:
        p.stop()


_atexit.register(_stop_bt_patches)

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from gateway.api.health import clear_health_cache  # noqa: E402
from gateway.core.database import get_engine  # noqa: E402
from gateway.core.redis import get_redis  # noqa: E402
from gateway.main import app  # noqa: E402
from gateway.models import Base  # noqa: E402
from gateway.routing.metagraph_sync import MetagraphManager  # noqa: E402
from gateway.routing.selector import MinerSelector  # noqa: E402
from gateway.services.auth_service import create_jwt_token  # noqa: E402

# Set up mock Bittensor state on app.state so health endpoint can access it
# (lifespan does not run with ASGITransport test client)
_test_metagraph_manager = MetagraphManager(subtensor=_mock_bt_subtensor, sync_interval=120)
_test_metagraph_manager.register_subnet(1)
# Mark the subnet as freshly synced so health endpoint doesn't report stale
import time as _time  # noqa: E402

_sn1_state = _test_metagraph_manager.get_state(1)
assert _sn1_state is not None
_sn1_state.metagraph = _mock_metagraph
_sn1_state.last_sync_time = _time.time()
app.state.metagraph_manager = _test_metagraph_manager
app.state.miner_selector = MinerSelector(_test_metagraph_manager)
app.state.dendrite = _mock_bt_dendrite


@pytest.fixture(scope="session", autouse=True)
async def _create_tables() -> None:
    """Recreate all tables from model metadata at test session start."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _flush_test_state() -> None:
    """Truncate DB tables and flush Redis test keys."""
    clear_health_cache()
    engine = get_engine()
    redis = await get_redis()
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} CASCADE"))
    for pattern in ("auth_rate:*", "api_key:*", "api_key_revoked:*"):
        keys = [k async for k in redis.scan_iter(pattern, count=1000)]
        if keys:
            await redis.delete(*keys)


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncGenerator[None, None]:
    """Truncate DB tables and flush Redis test keys before and after each test."""
    await _flush_test_state()
    yield
    await _flush_test_state()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def jwt_token() -> str:
    """Create a JWT for a non-existent org — JWT validation tests only."""
    return create_jwt_token("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def auth_headers(jwt_token: str) -> dict[str, str]:
    """Headers with JWT auth for dashboard endpoints (non-existent org — JWT validation only)."""
    return {"Authorization": f"Bearer {jwt_token}"}
