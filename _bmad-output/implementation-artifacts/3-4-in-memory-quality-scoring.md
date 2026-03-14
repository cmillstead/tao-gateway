# Story 3.4: In-Memory Quality Scoring

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want miner quality tracked without persisting request/response content,
so that routing decisions improve over time while respecting data privacy.

## Acceptance Criteria

1. **Given** a successful miner response
   **When** the gateway processes the response
   **Then** a numeric quality score is computed in-memory based on response validity, latency, and completeness (FR43)
   **And** no request or response content is persisted for scoring purposes

2. **Given** the in-memory miner scores
   **When** the score flush background task fires
   **Then** only numeric scores and metadata (miner UID, subnet, timestamp) are written to the `miner_scores` table
   **And** scores are maintained as a rolling 30-day window (NFR27)

3. **Given** sampled responses for quality scoring
   **When** a response is sampled (~5-10% of requests)
   **Then** the content is evaluated in-memory and immediately discarded after scoring
   **And** only the resulting numeric score persists

4. **Given** the miner scores in the database
   **When** the MinerSelector routes a request
   **Then** it can incorporate historical quality scores alongside metagraph incentive scores for better routing decisions

## Tasks / Subtasks

- [x] Task 1: Create MinerScorer in-memory scoring engine (AC: #1, #3)
  - [x] 1.1 Create `gateway/routing/scorer.py` with `MinerScorer` class
  - [x] 1.2 Implement `ScoreObservation` dataclass: `miner_uid: int`, `hotkey: str`, `netuid: int`, `success: bool`, `latency_ms: float`, `response_valid: bool`, `response_complete: bool`, `timestamp: datetime`
  - [x] 1.3 Implement `MinerQualityScore` dataclass for per-miner aggregated state: `total_requests: int`, `successful_requests: int`, `avg_latency_ms: float`, `quality_score: float` (0.0-1.0), `last_updated: datetime`
  - [x] 1.4 Implement `record_observation(observation: ScoreObservation)` — updates in-memory score using exponential moving average (EMA) with configurable alpha
  - [x] 1.5 Implement scoring formula: `quality = alpha * new_score + (1 - alpha) * old_score` where `new_score` factors in success (0/1), latency (normalized against subnet timeout), and response completeness
  - [x] 1.6 Implement `get_score(netuid: int, miner_uid: int) -> float | None` — returns current quality score
  - [x] 1.7 Implement `get_scores(netuid: int) -> dict[int, float]` — returns all scores for a subnet
  - [x] 1.8 Implement `get_snapshot_and_reset() -> list[MinerQualityScore]` — returns current scores for DB flush and resets observation counters (not scores themselves)

- [x] Task 2: Create miner_scores database model and migration (AC: #2)
  - [x] 2.1 Create `gateway/models/miner_score.py` with `MinerScore` SQLAlchemy model: `id`, `miner_uid`, `hotkey`, `netuid`, `quality_score`, `total_requests`, `successful_requests`, `avg_latency_ms`, `observation_count`, `created_at`, `updated_at`
  - [x] 2.2 Add composite unique constraint on `(hotkey, netuid)` for upsert operations
  - [x] 2.3 Add index on `(netuid, quality_score)` for efficient per-subnet score lookup
  - [x] 2.4 Generate Alembic migration for the new table
  - [x] 2.5 Add 30-day rolling window cleanup: `updated_at` older than 30 days gets deleted by the flush task

- [x] Task 3: Create score flush background task (AC: #2)
  - [x] 3.1 Create `gateway/tasks/` directory with `__init__.py`
  - [x] 3.2 Create `gateway/tasks/score_flush.py` with `ScoreFlushTask` class following `MetagraphManager` lifecycle pattern
  - [x] 3.3 Implement `start()` / `stop()` lifecycle using `asyncio.create_task` for background loop
  - [x] 3.4 Implement flush logic: call `scorer.get_snapshot_and_reset()`, upsert each score into `miner_scores` table using async SQLAlchemy
  - [x] 3.5 Implement 30-day cleanup: delete `miner_scores` rows where `updated_at < now() - 30 days` on each flush cycle
  - [x] 3.6 Default flush interval: 60 seconds (configurable via `Settings.score_flush_interval_seconds`)
  - [x] 3.7 Register task in `gateway/main.py` lifespan alongside existing MetagraphManager start/stop

- [x] Task 4: Hook scoring into BaseAdapter (AC: #1, #3)
  - [x] 4.1 Add `scorer: MinerScorer | None` parameter to `BaseAdapter.execute()` and `execute_stream()`
  - [x] 4.2 After successful response in `execute()`: create `ScoreObservation(success=True, latency_ms=elapsed, response_valid=True, response_complete=True)` and call `scorer.record_observation()`
  - [x] 4.3 On miner timeout/failure in `execute()`: create `ScoreObservation(success=False, ...)` and call `scorer.record_observation()` before raising exception
  - [x] 4.4 Same pattern for `execute_stream()` — score on stream completion or failure
  - [x] 4.5 Implement content sampling (~5-10%): use `random.random() < settings.quality_sample_rate` to decide if content is evaluated for completeness; if not sampled, `response_complete=None` (not factored into completeness score)
  - [x] 4.6 Update all route handlers (`chat.py`, `images.py`, `code.py`) to pass `scorer` from `app.state` to adapter `execute()` / `execute_stream()` calls

- [x] Task 5: Integrate quality scores into MinerSelector (AC: #4)
  - [x] 5.1 Add `scorer: MinerScorer | None` parameter to `MinerSelector.__init__()` (optional — graceful if None)
  - [x] 5.2 Modify `select_miner()` to blend incentive + quality: `blended_weight = incentive * (1 - quality_weight) + quality_score * quality_weight` where `quality_weight` is configurable (default 0.3)
  - [x] 5.3 If no quality score exists for a miner, use incentive-only weight (no penalty for unscored miners)
  - [x] 5.4 Add `quality_weight` setting to `Settings` class (default: 0.3)

- [x] Task 6: Add scoring configuration to Settings (AC: all)
  - [x] 6.1 Add `score_ema_alpha: float = 0.3` — EMA decay factor for quality scores
  - [x] 6.2 Add `score_flush_interval_seconds: int = 60` — how often to flush scores to DB
  - [x] 6.3 Add `quality_sample_rate: float = 0.1` — fraction of responses sampled for content scoring (10%)
  - [x] 6.4 Add `quality_weight: float = 0.3` — weight of quality score vs metagraph incentive in routing
  - [x] 6.5 Add `score_retention_days: int = 30` — rolling window for miner score retention

- [x] Task 7: Write tests (AC: all)
  - [x] 7.1 Create `tests/routing/test_scorer.py` — unit tests for MinerScorer (12 tests)
    - Test `record_observation` updates in-memory score
    - Test EMA calculation produces expected values after multiple observations
    - Test `get_score` returns None for unknown miner
    - Test `get_scores` returns all scores for a subnet
    - Test `get_snapshot_and_reset` returns scores and resets counters
    - Test scoring with success=True vs success=False
    - Test latency normalization
    - Test thread safety (concurrent observations)
  - [x] 7.2 Create `tests/models/test_miner_score.py` — model tests against real Postgres (3 tests)
    - Test create/read/update miner score record
    - Test unique constraint on (hotkey, netuid)
    - Test index exists on (netuid, quality_score)
  - [x] 7.3 Create `tests/tasks/test_score_flush.py` — integration tests (5 tests)
    - Test flush writes in-memory scores to DB (real Postgres)
    - Test 30-day cleanup deletes old scores
    - Test flush task start/stop lifecycle
    - Test flush with empty scores (no-op, no errors)
  - [x] 7.4 Extend `tests/routing/test_selector.py` — quality-blended selection (3 tests)
    - Test blended weights use both incentive and quality score
    - Test unscored miners use incentive-only weight
    - Test quality_weight=0 behaves like current incentive-only selection
  - [x] 7.5 Extend existing adapter tests — verify scoring hook is called on success and failure (4 tests)
  - [x] 7.6 Integration test: full request flow covered by adapter scoring + flush task tests

## Dev Notes

### Architecture Patterns and Constraints

- **In-memory first, DB flush second.** The scorer keeps all state in a Python dict. DB writes happen asynchronously in a background task, never in the request path. This ensures scoring adds <1ms to request latency.
- **EMA-based scoring** — architecture doc explicitly calls out EMA. Use `score = alpha * new + (1 - alpha) * old`. Alpha=0.3 means recent observations have ~30% weight, old scores decay exponentially.
- **No content persistence** — FR43 is explicit: "computes quality scores in-memory without persisting request/response content." Content is evaluated in-memory and immediately discarded. Only numeric scores and metadata persist.
- **Background task pattern** — follow `MetagraphManager` exactly: `asyncio.create_task` in lifespan, `start()`/`stop()` lifecycle, structured logging. See `gateway/routing/metagraph_sync.py` for the reference implementation.
- **Dependency injection** — `MinerScorer` should be a singleton on `app.state.scorer`, same as `app.state.metagraph_manager` and `app.state.miner_selector`. Pass to adapters via `Depends()` or explicit parameter.
- **Structlog only** — never `print()` or stdlib `logging`. Use `structlog.get_logger()` bound loggers.
- **Async SQLAlchemy** — all DB operations use `async with session` pattern. See existing models for reference.

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/routing/selector.py`** — `MinerSelector` class with weighted random selection via `random.choices`. Currently uses incentive-only weights from metagraph. Modify `select_miner()` to blend with quality scores. Cache invalidation already works via `sync_generation` counter — quality score changes should also invalidate the cache.
- **`gateway/routing/metagraph_sync.py`** — `MetagraphManager` with background task lifecycle (`start()`/`stop()`), `_sync_loop()` pattern, structured error handling. Follow this exact pattern for `ScoreFlushTask`.
- **`gateway/subnets/base.py`** — `BaseAdapter.execute()` and `execute_stream()` are the natural hook points. They already track `elapsed` time (via `time.perf_counter()`), know the `miner_uid`, and distinguish success from timeout/error.
- **`gateway/models/base.py`** — SQLAlchemy declarative Base. Import `Base` from here for the new `MinerScore` model.
- **`gateway/core/database.py`** — `AsyncSessionFactory` for creating DB sessions. Use `async_session_factory()` in the flush task.
- **`gateway/core/config.py`** — `Settings` class for all configuration. Add scoring-related settings here.
- **`gateway/main.py`** — Lifespan management. `MetagraphManager` is started/stopped in the lifespan context manager. Add `ScoreFlushTask` similarly.
- **`tests/conftest.py`** — Shared fixtures for real Postgres, Redis, and app client. Reuse these for scoring tests.

### What NOT to Touch

- Do NOT modify the error envelope format (Story 3.2 owns this)
- Do NOT modify rate limiting logic (Story 3.1 owns this)
- Do NOT modify auth flow or API key generation (Epic 1 owns this)
- Do NOT modify log redaction (Story 3.3 owns this — it's working correctly)
- Do NOT persist request/response content anywhere — scoring is in-memory only (FR43)
- Do NOT add complex ML-based scoring — stick to EMA over success/latency/completeness
- Do NOT change the `BaseAdapter` interface signature for existing callers if possible — `scorer` should be an optional parameter with `None` default

### Scoring Formula Reference

```python
# Per-observation score (0.0 to 1.0):
observation_score = (
    success_weight * float(success)  # 0.5 weight
    + latency_weight * max(0, 1 - (latency_ms / subnet_timeout_ms))  # 0.3 weight
    + completeness_weight * float(response_complete or 1.0)  # 0.2 weight
)

# EMA update:
new_quality = alpha * observation_score + (1 - alpha) * old_quality
```

Success dominates (50% weight) because failed/timed-out miners should be deprioritized quickly. Latency is normalized against the subnet timeout so different subnets (SN1=12s, SN19=30s) are comparable. Completeness is binary (valid response structure) and only evaluated on sampled requests.

### Project Structure Notes

- New files: `gateway/routing/scorer.py`, `gateway/models/miner_score.py`, `gateway/tasks/__init__.py`, `gateway/tasks/score_flush.py`
- Modified files: `gateway/routing/selector.py`, `gateway/subnets/base.py`, `gateway/core/config.py`, `gateway/main.py`, `gateway/api/chat.py`, `gateway/api/images.py`, `gateway/api/code.py`
- Test files: `tests/routing/test_scorer.py`, `tests/models/test_miner_score.py`, `tests/tasks/test_score_flush.py`, extend `tests/routing/test_selector.py`
- Migration: new Alembic migration for `miner_scores` table
- Alignment: follows existing conventions — models in `gateway/models/`, routing in `gateway/routing/`, tasks in `gateway/tasks/`, tests mirror source tree

### Testing Standards

- **Real Postgres and Redis required** — use Docker test containers, never mock
- **Mock only Bittensor SDK** — everything else uses real infrastructure
- Run: `uv run pytest --tb=short -q`
- Lint: `uv run ruff check gateway/ tests/`
- Types: `uv run mypy gateway/`
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests
- 445 tests currently pass (as of Story 3.3) — this story must not break any existing tests

### Previous Story Intelligence (Story 3.3)

- **445 tests pass** — baseline for regression testing after Story 3.3 (up from 426 in Story 3.2)
- **Security headers middleware** was added as pure ASGI middleware — consider whether scoring hook follows same pattern or stays as a function call within `BaseAdapter`
- **Code review found issues in both rounds** — expect scrutiny on: thread safety of in-memory dict, proper async patterns in flush task, edge cases like empty metagraph or zero observations
- **Key patterns established**: structured logging with redaction, middleware lifecycle, test patterns with real Postgres/Redis
- **f-string anti-pattern was caught in 3.3** — never use f-strings in structlog calls, always structured key-value

### Git Intelligence (Recent Commits)

- `99ec4c1` Merge PR #29: Story 3.3 security hardening
- `b51dbf4` feat: add security hardening with log redaction, security headers, and TLS config (Story 3.3)
- `33eacdf` Merge PR #28: Story 3.2 error handling and response metadata
- `7107eba` feat: add error handling, validation errors, and response metadata (Story 3.2)
- `6f090d3` Merge PR #27: Story 3.1 rate limiting engine
- Pattern: feature branches merged via PR. Branch naming: `feat/story-X.Y-description`. Each story is one commit + merge.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.4]
- [Source: _bmad-output/planning-artifacts/architecture.md#Miner Routing, Data Architecture, Background Tasks]
- [Source: _bmad-output/planning-artifacts/prd.md#FR43, FR28, FR29, FR30, NFR27]
- [Source: gateway/routing/selector.py — MinerSelector with incentive-only weighted selection]
- [Source: gateway/routing/metagraph_sync.py — MetagraphManager background task lifecycle pattern]
- [Source: gateway/subnets/base.py — BaseAdapter.execute() and execute_stream() hook points]
- [Source: gateway/core/config.py — Settings class for new scoring configuration]
- [Source: gateway/main.py — Lifespan context manager for task registration]
- [Source: gateway/models/base.py — SQLAlchemy Base for new MinerScore model]
- [Source: gateway/core/database.py — AsyncSessionFactory for flush task DB access]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Created `MinerScorer` in-memory scoring engine with EMA-based quality scoring. `ScoreObservation` and `MinerQualityScore` dataclasses, thread-safe `record_observation()`, `get_score()`, `get_scores()`, `get_snapshot_and_reset()`. Scoring formula: 50% success weight, 30% latency (normalized against subnet timeout), 20% completeness.
- Task 2: Created `MinerScore` SQLAlchemy model with composite unique constraint on `(hotkey, netuid)`, index on `(netuid, quality_score)`. Generated and applied Alembic migration `d918598f5b47_add_miner_scores_table`.
- Task 3: Created `ScoreFlushTask` background task following `MetagraphManager` lifecycle pattern. `flush_once()` upserts in-memory scores to DB and cleans up scores older than 30 days. `start()`/`stop()` lifecycle with final flush on shutdown.
- Task 4: Hooked scoring into `BaseAdapter.execute()` and `execute_stream()` via `_record_score()` helper. Records success/failure observations with latency. Updated `chat.py`, `images.py`, `code.py` route handlers to pass `scorer` from `app.state`.
- Task 5: Modified `MinerSelector.select_miner()` to blend incentive with quality scores: `blended = incentive * (1 - quality_weight) + quality_score * quality_weight`. Unscored miners use incentive-only weight.
- Task 6: Added 5 scoring settings to `Settings`: `score_ema_alpha`, `score_flush_interval_seconds`, `quality_sample_rate`, `quality_weight`, `score_retention_days`. Wired scorer and flush task into `main.py` lifespan.
- Task 7: 31 new tests across 5 test files. 476 total tests pass (up from 445). Ruff clean, mypy clean.

### Change Log

- 2026-03-14: Story 3.4 implementation complete — in-memory quality scoring with EMA, DB persistence via flush task, quality-blended miner selection, full test coverage
- 2026-03-14: Code review #1 — 7 issues fixed (2 HIGH, 3 MEDIUM, 2 LOW): implemented content sampling with quality_sample_rate, changed scorer key from miner_uid to hotkey, added Pydantic validators for scoring config, replaced N+1 flush with upsert, removed redundant observation_count column, removed unused logger
- 2026-03-14: Code review #2 — 2 issues fixed (1 MEDIUM, 1 LOW): client disconnect in streaming no longer records as success, added ge=1 constraints on score_flush_interval_seconds and score_retention_days

### File List

New files:
- gateway/routing/scorer.py — MinerScorer with EMA-based in-memory quality scoring
- gateway/models/miner_score.py — MinerScore SQLAlchemy model with TimestampMixin
- gateway/tasks/__init__.py — Tasks package
- gateway/tasks/score_flush.py — ScoreFlushTask background task for DB persistence
- migrations/versions/d918598f5b47_add_miner_scores_table.py — Alembic migration
- migrations/versions/c15784f7f7bb_drop_observation_count_from_miner_scores.py — Alembic migration (review fix)
- tests/routing/test_scorer.py — 12 tests for MinerScorer
- tests/models/test_miner_score.py — 3 tests for MinerScore model
- tests/tasks/__init__.py — Test tasks package
- tests/tasks/test_score_flush.py — 5 tests for ScoreFlushTask

Modified files:
- gateway/routing/selector.py — Added scorer and quality_weight params, blended weight selection
- gateway/subnets/base.py — Added _record_score() helper, scorer param to execute/execute_stream
- gateway/core/config.py — Added 5 scoring configuration fields
- gateway/main.py — Added MinerScorer, ScoreFlushTask to lifespan
- gateway/models/__init__.py — Added MinerScore to exports
- gateway/api/chat.py — Pass scorer to adapter execute/execute_stream
- gateway/api/images.py — Pass scorer to adapter execute
- gateway/api/code.py — Pass scorer to adapter execute
- tests/routing/test_selector.py — 3 new quality-blended selection tests
- tests/subnets/test_base_adapter.py — 4 new scoring hook tests
