# Code Scan Implementation Plan — 2026-03-13

**Source**: tao-gateway Code Scan 2026-03-13 (vault)
**Total tasks**: 19 | **Total tests to add**: ~18 | **Findings**: 0 CRIT, 2 HIGH, 10 MED, 10 LOW

---

## Phase 1: HIGH Priority (2 tasks)

### Task 1.1 — Weighted miner selection (CODE-HIGH-1)
- **Files**: `gateway/routing/selector.py`
- **Fix**: Replace `eligible[0]` with `random.choices(eligible, weights=...)` for weighted random selection by incentive score.
- **Tests to add**: 2 — distribution follows weights over N=1000 selections; zero-incentive miners never selected.

### Task 1.2 — Test JWT sub claim validation (SEC-HIGH-1)
- **Files**: `tests/middleware/test_auth_middleware.py`
- **Fix**: Add test for non-UUID `sub` claim in JWT. The code already handles this; just needs test coverage.
- **Tests to add**: 1 — `test_get_current_org_id_rejects_non_uuid_sub`.

---

## Phase 2: MED Priority (10 tasks)

### Task 2.1 — Wrap `close_redis()` in shutdown guard + test (TEST-MED-3, CODE-MED-4)
- **Files**: `gateway/main.py`, `gateway/core/redis.py`, `tests/core/test_lifespan.py`
- **Fix**: (1) Add try/except around `close_redis()` in lifespan shutdown. (2) Extract shared `_close_client` in redis.py. (3) Add shutdown resilience test.
- **Tests to add**: 2

### Task 2.2 — Add `environment` column to ApiKey model (CODE-MED-5)
- **Files**: `gateway/models/api_key.py`, `gateway/services/api_key_service.py`, `gateway/schemas/api_keys.py`
- **Fix**: Add `environment` column, populate on create, expose in list schema.
- **Tests to add**: 2 — create with env, filter by env.

### Task 2.3 — Make pool sizes configurable (CODE-MED-6)
- **Files**: `gateway/core/config.py`, `gateway/core/database.py`, `gateway/core/redis.py`
- **Fix**: Add `db_pool_size`, `db_max_overflow`, `redis_max_connections` to Settings.
- **Tests to add**: 1 — test settings forwarded to engine.

### Task 2.4 — Extract rehash helper (CODE-MED-7)
- **Files**: `gateway/core/security.py`, `gateway/services/auth_service.py`, `gateway/middleware/auth.py`
- **Fix**: Extract `try_rehash()` into security.py, replace both call sites.
- **Tests to add**: 2 — success and failure paths.

### Task 2.5 — Co-locate cache/tombstone TTL constants (CODE-MED-8)
- **Files**: `gateway/middleware/auth.py`, `gateway/services/api_key_service.py`
- **Fix**: Move both constants to shared location, add assertion.
- **Tests to add**: 0 — assertion is self-testing.

### Task 2.6 — Test auth middleware cache corruption paths (TEST-MED-1)
- **Files**: `tests/middleware/test_auth_middleware.py`
- **Fix**: Add tests for UnicodeDecodeError and ValueError/IndexError cache corruption recovery.
- **Tests to add**: 2

### Task 2.7 — Test `try_get_redis()` and `reset_redis()` (TEST-MED-2)
- **Files**: `tests/core/test_redis.py`
- **Fix**: Add 3 dedicated tests for Redis helper functions.
- **Tests to add**: 3

### Task 2.8 — Fix flaky timing-dependent test (TEST-MED-4)
- **Files**: `tests/routing/test_metagraph_sync.py`
- **Fix**: Replace `asyncio.sleep(0.1)` with event-based synchronization.
- **Tests to add**: 0 — refactor existing test.

### Task 2.9 — Initialize Alembic (CODE-MED-2)
- **Files**: Project root (alembic config), `gateway/core/database.py`
- **Fix**: `alembic init`, configure async engine, create initial migration.
- **Tests to add**: 1 — upgrade on empty DB produces expected schema.

### Task 2.10 — Add `reset_settings()` for test isolation (CODE-MED-3)
- **Files**: `gateway/core/config.py`
- **Fix**: Add function to clear LRU cache and re-create settings.
- **Tests to add**: 1

---

## Phase 3: LOW Priority (7 tasks)

### Task 3.1 — Rename `_sse_error` to `sse_error` (CODE-LOW-1)
- **Files**: `gateway/subnets/base.py`, `gateway/api/chat.py`

### Task 3.2 — Add type annotations to chat.py (CODE-LOW-2)
- **Files**: `gateway/api/chat.py`

### Task 3.3 — Move deferred imports to top of registry.py (CODE-LOW-3)
- **Files**: `gateway/subnets/registry.py`

### Task 3.4 — Define `SSE_DONE` constant (CODE-LOW-5)
- **Files**: `gateway/subnets/base.py`, `gateway/api/chat.py`

### Task 3.5 — Inline `_try_get_redis_for_health` (CODE-LOW-6)
- **Files**: `gateway/api/health.py`

### Task 3.6 — Create TimestampMixin (CODE-LOW-7)
- **Files**: `gateway/models/base.py`, `gateway/models/api_key.py`, `gateway/models/organization.py`

### Task 3.7 — Fix double `model_dump()` call (CODE-LOW-9)
- **Files**: `gateway/api/health.py`

### Deferred (no action needed now)
- CODE-LOW-4: ErrorResponse schemas — defer until OpenAPI docs are prioritized
- CODE-LOW-8: Empty tasks/ package — remove when convenient
- CODE-MED-1: Global mutable state — acceptable for MVP, revisit for multi-tenant
