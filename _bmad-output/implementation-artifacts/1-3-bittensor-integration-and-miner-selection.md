# Story 1.3: Bittensor Integration & Miner Selection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the gateway to connect to the Bittensor network and select quality miners,
So that my requests are routed to responsive, high-quality miners.

## Acceptance Criteria

1. **Given** the gateway starts up, **when** the FastAPI lifespan initializes, **then** the Bittensor wallet (coldkey + SN1 hotkey) is loaded from the configured path, **and** the Dendrite client is initialized and stored in `app.state`, **and** the metagraph for SN1 is synced and stored in `app.state`.

2. **Given** the gateway is running, **when** the metagraph background sync task fires (every 2 minutes), **then** the metagraph is refreshed from the network within 30 seconds (NFR5), **and** request handling is not blocked during sync, **and** the sync timestamp is recorded for staleness tracking.

3. **Given** the metagraph sync fails, **when** the network is unreachable or times out, **then** the gateway continues operating on the cached metagraph state (NFR21, NFR25), **and** a warning is logged with structured metadata, **and** the `/v1/health` endpoint reports metagraph staleness.

4. **Given** a request needs miner selection for SN1, **when** the MinerSelector is called, **then** it returns the top miner by incentive score from the current metagraph, **and** miners with zero incentive or known-offline status are excluded (FR30).

5. **Given** wallet files on disk, **when** the gateway accesses them, **then** the coldkey is encrypted at rest (NFR9), **and** hotkeys are isolated per subnet, **and** neither coldkey nor hotkey content appears in any log output.

## Tasks / Subtasks

- [x] Task 1: Bittensor configuration settings (AC: #1, #5)
  - [x] 1.1: Add Bittensor-specific settings to `gateway/core/config.py` — `hotkey_name`, `sn1_netuid`, `metagraph_sync_interval_seconds`, `dendrite_timeout_seconds`, `subtensor_network`
  - [x] 1.2: Add `.env.example` entries for all new settings

- [x] Task 2: Bittensor SDK initialization module (AC: #1, #5)
  - [x] 2.1: Create `gateway/core/bittensor.py` — wallet loading, subtensor connection, dendrite initialization
  - [x] 2.2: Wallet loads from `settings.wallet_path` / `settings.wallet_name` with hotkey from `settings.hotkey_name`
  - [x] 2.3: Dendrite created from wallet, stored as singleton via `app.state`
  - [x] 2.4: Ensure no wallet key material (coldkey, hotkey) ever appears in logs — use structlog redaction
  - [x] 2.5: Handle SDK initialization failures gracefully (log error, raise on startup)

- [x] Task 3: Metagraph sync background task (AC: #2, #3)
  - [x] 3.1: Create `gateway/routing/metagraph_sync.py` — `MetagraphManager` class managing per-subnet metagraph state
  - [x] 3.2: Implement `sync()` method: calls `subtensor.metagraph(netuid=...)`, stores result with timestamp
  - [x] 3.3: Implement `start_sync_loop()`: asyncio background task firing every `metagraph_sync_interval_seconds` (default 120s)
  - [x] 3.4: Sync must not block request handling — run in background `asyncio.create_task()`
  - [x] 3.5: On sync failure: log warning with `structlog`, keep cached metagraph, record failure timestamp
  - [x] 3.6: Expose `last_sync_time`, `is_stale` (>5min since last sync), `sync_error` for health endpoint

- [x] Task 4: Miner selector (AC: #4)
  - [x] 4.1: Create `gateway/routing/selector.py` — `MinerSelector` class
  - [x] 4.2: Implement `select_miner(netuid: int)` → returns `AxonInfo` of top miner by incentive score
  - [x] 4.3: Filter out miners with zero incentive, zero stake, or unresponsive axons (no IP/port)
  - [x] 4.4: Raise `SubnetUnavailableError` when no eligible miners found
  - [x] 4.5: Log selected miner UID (but never log axon connection details beyond UID)

- [x] Task 5: Lifespan integration (AC: #1, #2)
  - [x] 5.1: Update `gateway/main.py` lifespan — initialize wallet, dendrite, metagraph, start sync loop
  - [x] 5.2: Store in `app.state`: `dendrite`, `metagraph_manager`, `miner_selector`
  - [x] 5.3: Shutdown: cancel sync task, close dendrite (if applicable)

- [x] Task 6: Health endpoint enhancement (AC: #3)
  - [x] 6.1: Update `gateway/schemas/health.py` — add `metagraph` field with per-subnet sync status (last_sync, is_stale, sync_error)
  - [x] 6.2: Update `gateway/api/health.py` — include metagraph status from `app.state.metagraph_manager`
  - [x] 6.3: If metagraph is stale (>5min), health endpoint returns `degraded` status

- [x] Task 7: Tests (AC: all)
  - [x] 7.1: Create `tests/routing/test_metagraph_sync.py` — test sync success, sync failure (cached fallback), staleness detection, sync interval timing
  - [x] 7.2: Create `tests/routing/test_selector.py` — test miner selection by incentive, zero-incentive exclusion, no-miners-available (SubnetUnavailableError), offline miner exclusion
  - [x] 7.3: Create `tests/core/test_bittensor.py` — test wallet loading, dendrite creation, initialization failure handling
  - [x] 7.4: Update `tests/api/test_health.py` — test health endpoint with metagraph status, stale metagraph → degraded
  - [x] 7.5: Verify `uv run pytest` passes with all new + existing tests (86 passed)
  - [x] 7.6: Verify `uv run ruff check` and `uv run mypy gateway` pass with zero errors (in new code; pre-existing issues in redis.py and api_keys.py remain)

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Bittensor SDK Initialization Pattern

```python
# gateway/core/bittensor.py
import bittensor as bt
import structlog

from gateway.core.config import settings

logger = structlog.get_logger()

def create_wallet() -> bt.Wallet:
    """Load wallet from configured path. Coldkey must be encrypted at rest."""
    wallet = bt.Wallet(
        name=settings.wallet_name,
        path=settings.wallet_path,
        hotkey=settings.hotkey_name,
    )
    logger.info("wallet_loaded", wallet_name=settings.wallet_name)
    # NEVER log wallet key material — coldkey, hotkey, ss58 addresses are sensitive
    return wallet

def create_subtensor() -> bt.Subtensor:
    """Connect to Bittensor network."""
    subtensor = bt.Subtensor(network=settings.subtensor_network)
    logger.info("subtensor_connected", network=settings.subtensor_network)
    return subtensor

def create_dendrite(wallet: bt.Wallet) -> bt.Dendrite:
    """Create Dendrite client for querying miners."""
    dendrite = bt.Dendrite(wallet=wallet)
    logger.info("dendrite_initialized")
    return dendrite
```

**CRITICAL:** The Bittensor SDK uses Pydantic v2 internally for Synapse models. Our Pydantic schemas are separate — never import or inherit from SDK Synapse models in our schema layer.

#### Metagraph Manager Pattern

```python
# gateway/routing/metagraph_sync.py
import asyncio
import time
from dataclasses import dataclass, field

import bittensor as bt
import structlog

logger = structlog.get_logger()

@dataclass
class SubnetMetagraphState:
    """Per-subnet metagraph state with sync tracking."""
    netuid: int
    metagraph: bt.Metagraph | None = None
    last_sync_time: float = 0.0
    last_sync_error: str | None = None
    consecutive_failures: int = 0

    @property
    def is_stale(self) -> bool:
        """Metagraph is stale if >5 minutes since last successful sync."""
        if self.metagraph is None:
            return True
        return (time.time() - self.last_sync_time) > 300  # 5 minutes

class MetagraphManager:
    """Manages metagraph state for all registered subnets."""

    def __init__(self, subtensor: bt.Subtensor, sync_interval: int = 120) -> None:
        self._subtensor = subtensor
        self._sync_interval = sync_interval
        self._subnets: dict[int, SubnetMetagraphState] = {}
        self._sync_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def register_subnet(self, netuid: int) -> None:
        self._subnets[netuid] = SubnetMetagraphState(netuid=netuid)

    def get_metagraph(self, netuid: int) -> bt.Metagraph | None:
        state = self._subnets.get(netuid)
        return state.metagraph if state else None

    def get_state(self, netuid: int) -> SubnetMetagraphState | None:
        return self._subnets.get(netuid)

    async def sync_all(self) -> None:
        """Sync all registered subnet metagraphs."""
        for netuid, state in self._subnets.items():
            try:
                # Run sync in executor to avoid blocking the event loop
                # (subtensor.metagraph() is a blocking call)
                loop = asyncio.get_event_loop()
                metagraph = await loop.run_in_executor(
                    None, self._subtensor.metagraph, netuid
                )
                state.metagraph = metagraph
                state.last_sync_time = time.time()
                state.last_sync_error = None
                state.consecutive_failures = 0
                logger.info(
                    "metagraph_synced",
                    netuid=netuid,
                    neurons=int(metagraph.n),
                )
            except Exception as exc:
                state.consecutive_failures += 1
                state.last_sync_error = str(exc)
                logger.warning(
                    "metagraph_sync_failed",
                    netuid=netuid,
                    error=str(exc),
                    consecutive_failures=state.consecutive_failures,
                )

    async def start_sync_loop(self) -> None:
        """Start background sync loop. Call as asyncio.create_task()."""
        # Initial sync on startup
        await self.sync_all()
        while True:
            await asyncio.sleep(self._sync_interval)
            await self.sync_all()

    def start(self) -> None:
        """Create background task for sync loop."""
        self._sync_task = asyncio.create_task(self.start_sync_loop())

    async def stop(self) -> None:
        """Cancel sync task on shutdown."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
```

**CRITICAL:** `subtensor.metagraph(netuid)` is a **blocking** call (network I/O to chain). MUST run in `loop.run_in_executor()` to avoid blocking the async event loop. Never call it directly in an async handler.

#### Miner Selector Pattern

```python
# gateway/routing/selector.py
import bittensor as bt
import structlog

from gateway.core.exceptions import SubnetUnavailableError
from gateway.routing.metagraph_sync import MetagraphManager

logger = structlog.get_logger()

class MinerSelector:
    """Selects the best miner for a given subnet based on metagraph incentive scores."""

    def __init__(self, metagraph_manager: MetagraphManager) -> None:
        self._metagraph_manager = metagraph_manager

    def select_miner(self, netuid: int) -> bt.AxonInfo:
        """Select the top miner by incentive score, excluding ineligible miners.

        Raises SubnetUnavailableError if no eligible miners are found.
        """
        metagraph = self._metagraph_manager.get_metagraph(netuid)
        if metagraph is None:
            raise SubnetUnavailableError(f"sn{netuid}")

        # Build list of eligible miners
        eligible: list[tuple[int, float, bt.AxonInfo]] = []
        for uid in range(int(metagraph.n)):
            incentive = float(metagraph.incentive[uid])
            axon = metagraph.axons[uid]

            # Skip miners with zero incentive (not actively mining)
            if incentive <= 0:
                continue
            # Skip miners with no reachable axon (no IP or port 0)
            if not axon.ip or axon.port == 0:
                continue

            eligible.append((uid, incentive, axon))

        if not eligible:
            raise SubnetUnavailableError(f"sn{netuid}")

        # Sort by incentive descending, pick the top one
        eligible.sort(key=lambda x: x[1], reverse=True)
        best_uid, best_incentive, best_axon = eligible[0]

        logger.info(
            "miner_selected",
            netuid=netuid,
            miner_uid=best_uid,
            incentive=round(best_incentive, 6),
            eligible_count=len(eligible),
        )
        return best_axon
```

**Note:** This is the MVP miner selection — pick the highest-incentive miner. Phase 2 adds EMA-based scoring (`gateway/routing/scorer.py`) and potentially k-of-n multi-miner querying. For now, keep it simple.

#### Lifespan Integration

```python
# gateway/main.py — lifespan additions
# After existing DB/Redis checks, add:

from gateway.core.bittensor import create_wallet, create_subtensor, create_dendrite
from gateway.routing.metagraph_sync import MetagraphManager
from gateway.routing.selector import MinerSelector

# Inside lifespan, after Redis check:
wallet = create_wallet()
subtensor = create_subtensor()
dendrite = create_dendrite(wallet)

metagraph_manager = MetagraphManager(
    subtensor=subtensor,
    sync_interval=settings.metagraph_sync_interval_seconds,
)
metagraph_manager.register_subnet(settings.sn1_netuid)
metagraph_manager.start()

miner_selector = MinerSelector(metagraph_manager)

app.state.dendrite = dendrite
app.state.metagraph_manager = metagraph_manager
app.state.miner_selector = miner_selector

# In shutdown:
await metagraph_manager.stop()
```

**CRITICAL:** Use `app.state` for singletons (architecture mandate). Never use module-level globals for mutable state.

#### Health Endpoint Enhancement

```python
# gateway/schemas/health.py — additions
from pydantic import BaseModel

class SubnetHealthStatus(BaseModel):
    netuid: int
    last_sync: str | None = None  # ISO 8601
    is_stale: bool = True
    sync_error: str | None = None

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str = "unknown"
    redis: str = "unknown"
    metagraph: dict[str, SubnetHealthStatus] | None = None
```

Health endpoint should report `degraded` if any metagraph is stale (>5min since last sync).

#### Config Additions

```python
# gateway/core/config.py — new settings
class Settings(BaseSettings):
    # ... existing settings ...

    # Bittensor
    wallet_name: str = "default"
    wallet_path: str = "~/.bittensor/wallets"
    hotkey_name: str = "default"
    subtensor_network: str = "finney"  # "finney" = mainnet, "test" = testnet
    sn1_netuid: int = 1
    metagraph_sync_interval_seconds: int = 120  # 2 minutes
    dendrite_timeout_seconds: int = 30
```

#### Test Strategy

Tests for this story require **mocking the Bittensor SDK** — we cannot hit the real Bittensor network in tests.

**Mock targets:**
- `bt.Wallet` — mock constructor, verify no key material logged
- `bt.Subtensor` — mock `metagraph()` method to return fake metagraph data
- `bt.Dendrite` — mock constructor (usage in Story 1.4)
- `bt.Metagraph` — create minimal fake with `n`, `incentive`, `axons` attributes

**Use `unittest.mock.patch` or `monkeypatch` — NOT `fakebittensor` (no such library exists).**

Example mock metagraph fixture:
```python
import numpy as np

@pytest.fixture
def mock_metagraph():
    """Create a fake metagraph with controllable miner data."""
    metagraph = MagicMock()
    metagraph.n = 3  # int in SDK v10+
    metagraph.incentive = np.array([0.5, 0.0, 0.3])  # numpy ndarray in SDK v10+
    metagraph.axons = [
        MagicMock(ip="1.2.3.4", port=8091),   # UID 0: eligible
        MagicMock(ip="", port=0),               # UID 1: no axon
        MagicMock(ip="5.6.7.8", port=8091),    # UID 2: eligible
    ]
    return metagraph
```

**SDK v10+ Data Types (CRITICAL — do not use torch):**
- `metagraph.n` — `int` (number of neurons)
- `metagraph.incentive` — `numpy.ndarray` (float array indexed by UID)
- `metagraph.stake` — `numpy.ndarray`
- `metagraph.trust` — `numpy.ndarray`
- `metagraph.axons` — `list[bt.AxonInfo]` (each has `.ip`, `.port`, `.hotkey`, `.coldkey`)
- `metagraph.uids` — `numpy.ndarray` (int array of UIDs)

**Dendrite async usage (preferred for production):**
```python
# Use dendrite.forward() for async queries (not .query() which is sync)
responses = await dendrite.forward(
    axons=[axon],
    synapse=my_synapse,
    timeout=settings.dendrite_timeout_seconds,
)
```

**Metagraph re-sync (more efficient than creating new):**
```python
# Re-sync existing metagraph instead of creating new each time
metagraph.sync(subtensor=subtensor)
```

### Previous Story Intelligence (Story 1.2)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Error envelope format via `GatewayError` hierarchy + `gateway_exception_handler`
- Shared `PasswordHasher` in `gateway/core/security.py` (don't duplicate instances)
- Redis circuit breaker pattern in `gateway/core/redis.py`
- Health endpoint with in-memory cache (5s TTL)
- `ruff check` + `mypy` must pass with zero errors

**Learnings from adversarial code reviews:**
- Run `subtensor.metagraph()` in executor — it's blocking I/O
- Never log sensitive data (wallet keys) — add to structlog redaction patterns if needed
- Health endpoint already has cache — extend it, don't create parallel caching
- Tests need proper mocking — no real network calls
- Type ignore comments need justification comment
- Use `from __future__ import annotations` pattern sparingly — only where needed for forward refs

**Debug log references from Story 1.2:**
- `B008` ruff rule is already ignored (Depends() in defaults is FastAPI standard)
- `B904` — all except clauses use `raise ... from exc/None`
- mypy `bittensor.*` already set to `ignore_missing_imports`
- pytest-asyncio uses `asyncio_default_test_loop_scope = "session"`

### Library & Framework Requirements

| Library | Version | Why |
|---|---|---|
| `bittensor` | v10.1.0 (already installed) | Wallet, Subtensor, Dendrite, Metagraph — core SDK |
| `numpy` | (transitive via bittensor) | Metagraph data (incentive, trust, etc.) stored as numpy ndarrays in SDK v10+ |

No new dependencies needed — bittensor is already in pyproject.toml.

### Project Structure Notes

New files to create:
```
gateway/
├── core/
│   └── bittensor.py           # SDK init: wallet, subtensor, dendrite (NEW)
├── routing/
│   ├── metagraph_sync.py      # MetagraphManager + background sync loop (NEW)
│   └── selector.py            # MinerSelector: pick best miner by incentive (NEW)
└── tasks/
    └── metagraph.py           # (OPTIONAL — sync loop can live in metagraph_sync.py)

tests/
├── core/
│   └── test_bittensor.py      # Wallet loading, dendrite creation tests (NEW)
├── routing/
│   ├── test_metagraph_sync.py # Sync success/failure/staleness tests (NEW)
│   └── test_selector.py       # Miner selection tests (NEW)
└── api/
    └── test_health.py         # MODIFIED — add metagraph health tests
```

Modified files:
- `gateway/core/config.py` — add Bittensor settings (hotkey_name, sn1_netuid, sync_interval, dendrite_timeout, subtensor_network)
- `gateway/main.py` — lifespan: init wallet/subtensor/dendrite/metagraph_manager/miner_selector, start sync, store in app.state
- `gateway/schemas/health.py` — add SubnetHealthStatus, metagraph field
- `gateway/api/health.py` — include metagraph status in response
- `.env.example` — add new env vars
- `tests/conftest.py` — add mock bittensor fixtures if shared

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.3] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/architecture.md#Core-Architectural-Decisions] — Metagraph sync: shared in-memory, 2-min interval, cached fallback
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Adapter pattern: fat base + thin adapters, metagraph sync pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure-&-Boundaries] — File locations: core/bittensor.py, routing/selector.py, routing/metagraph_sync.py
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation-Patterns-&-Consistency-Rules] — Async patterns, dependency injection, logging
- [Source: _bmad-output/planning-artifacts/prd.md#FR28] — Miner selection by incentive score
- [Source: _bmad-output/planning-artifacts/prd.md#FR29] — Metagraph sync within 5 minutes
- [Source: _bmad-output/planning-artifacts/prd.md#FR30] — Detect and avoid offline miners
- [Source: _bmad-output/planning-artifacts/prd.md#NFR5] — Metagraph sync within 30s, non-blocking
- [Source: _bmad-output/planning-artifacts/prd.md#NFR9] — Coldkey encrypted, hotkeys isolated, neither in logs
- [Source: _bmad-output/planning-artifacts/prd.md#NFR21] — Continue on cached metagraph if sync fails
- [Source: _bmad-output/planning-artifacts/prd.md#NFR25] — Handle metagraph API unavailability (cached fallback)

## Change Log

- 2026-03-12: Story 1.3 implementation complete — Bittensor SDK integration, metagraph sync, miner selection, health endpoint enhancement, full test coverage
- 2026-03-12: Adversarial code review — 9 issues found and fixed (3 HIGH, 4 MEDIUM, 2 LOW): deprecated asyncio API, private attr access in health endpoint, missing startup error logging, wallet name log leak, silent initial sync failure, missing stake filtering, fragile test imports, hardcoded staleness threshold, test count clarification. 87 tests passing.
- 2026-03-12: Adversarial code review round 2 — 9 issues found and fixed (3 HIGH, 4 MEDIUM, 2 LOW): initial sync failure silently swallowed (H1), no escalation after repeated sync failures (H2), sync miner selection on event loop undocumented (H3), wallet_name missing from log (M1), health returns null vs empty dict ambiguity (M2), conftest patches never stopped (M3), async tests missing markers (M4), shared mutable state undocumented (L1), identical error messages for distinct failures (L2). 87 tests passing.
- 2026-03-12: Adversarial code review round 3 — 9 issues found and fixed (3 HIGH, 4 MEDIUM, 2 LOW): dendrite not closed on shutdown despite Task 5.3 marked done (H1), no test for log escalation after repeated sync failures (H2), test_start_and_stop doesn't verify background loop (H3), initial sync failure doesn't block startup (M1), get_all_states returns shared mutable references (M2), no test for missing metagraph_manager on app.state (M3), timing-dependent test fragile under CI (M4), conftest module-level shared state leaks between tests (L1), SubnetUnavailableError indistinguishable failure reasons (L2). 90 tests passing.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing ruff SIM105 in `gateway/core/redis.py` — not addressed (out of scope)
- Pre-existing mypy unused-ignore in `gateway/api/api_keys.py` — not addressed (out of scope)
- Bittensor SDK types use `ignore_missing_imports` in mypy config — no type-ignore comments needed on bt.* types

### Completion Notes List

- Task 1: Added 5 new Bittensor settings to `Settings` class and `.env.example`
- Task 2: Created `gateway/core/bittensor.py` with `create_wallet()`, `create_subtensor()`, `create_dendrite()` — follows architecture patterns exactly, never logs key material
- Task 3: Created `gateway/routing/metagraph_sync.py` with `SubnetMetagraphState` dataclass and `MetagraphManager` class — async sync via `run_in_executor()` to avoid blocking, cached fallback on failure, staleness tracking (>5min)
- Task 4: Created `gateway/routing/selector.py` with `MinerSelector` — selects top miner by incentive, filters zero-incentive, zero-stake, and offline miners, raises `SubnetUnavailableError` when no eligible miners
- Task 5: Updated `gateway/main.py` lifespan to initialize wallet/subtensor/dendrite/metagraph_manager/miner_selector, store in `app.state`, cancel sync on shutdown
- Task 6: Updated health schema with `SubnetHealthStatus` model and metagraph field; health endpoint reports `degraded` when any metagraph is stale
- Task 7: Added 31 new tests across 3 new test files + 2 new tests in existing `test_health.py`; updated `tests/conftest.py` with Bittensor SDK mocks for test isolation
- All 87 tests pass (31 story-specific + 56 pre-existing), ruff and mypy clean on new code

### File List

New files:
- gateway/core/bittensor.py
- gateway/routing/metagraph_sync.py
- gateway/routing/selector.py
- tests/core/__init__.py
- tests/core/test_bittensor.py
- tests/routing/test_metagraph_sync.py
- tests/routing/test_selector.py

Modified files:
- gateway/core/config.py
- gateway/main.py
- gateway/schemas/health.py
- gateway/api/health.py
- .env.example
- tests/conftest.py
- tests/api/test_health.py
