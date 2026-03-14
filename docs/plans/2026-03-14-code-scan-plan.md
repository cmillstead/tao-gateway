# Code Scan Implementation Plan — 2026-03-14

**Total tasks**: 17 findings (0 CRIT, 4 HIGH, 6 MED, 7 LOW)
**Total new tests**: ~25
**Vault doc**: `tao-gateway Code Scan 2026-03-14.md`

---

## Phase 1: HIGH Severity (4 tasks, ~12 new tests)

### Task 1: Fix validation error input value leak [SEC-HIGH-1]
- **Files**: `gateway/middleware/error_handler.py`
- **Fix**: Remove or redact `error.get("input")` from validation error responses. Apply `redact_string_value()` or omit entirely.
- **Tests (2)**: Verify password field not echoed, verify API key field not echoed in 422 response.

### Task 2: Fix `try_rehash` transaction commit bug [CODE-HIGH-1]
- **Files**: `gateway/core/security.py`
- **Fix**: Remove the `await db.commit()` after the `begin_nested()` context manager. Let savepoint handle it.
- **Tests (3)**: Rehash during active transaction doesn't commit outer tx; rehash failure doesn't rollback outer tx; argon2 parameters are pinned.

### Task 3: Add body size limiter tests [TEST-HIGH-1]
- **Files**: New `tests/middleware/test_body_size_limit.py`
- **Fix**: Test-only — no code changes.
- **Tests (4)**: Content-Length > 1MB (413), negative Content-Length (400), non-numeric Content-Length (400), normal request passes.

### Task 4: Add core/rate_limit.py tests [TEST-HIGH-2]
- **Files**: New `tests/core/test_rate_limit.py`
- **Fix**: Test-only — no code changes.
- **Tests (4)**: FallbackStore within/exceeding limit, window expiry, eviction above max entries, check_rate_limit Redis vs fallback paths.

---

## Phase 2: MED Severity (6 tasks, ~8 new tests)

### Task 5: Consolidate rate limit infrastructure [CODE-MED-1]
- **Files**: `gateway/core/rate_limit.py`, `gateway/middleware/rate_limit.py`
- **Fix**: Extract shared script cache utility. Rename `check_rate_limit` to `check_auth_rate_limit`. Document fail-open decision.
- **Tests (1)**: Redis disconnection test for both limiters.

### Task 6: Extract shared endpoint handler [CODE-MED-2]
- **Files**: `gateway/api/chat.py`, `gateway/api/images.py`, `gateway/api/code.py`
- **Fix**: Extract `execute_subnet_request()` helper. Each handler becomes ~5 lines.
- **Tests (0)**: Existing endpoint tests cover this.

### Task 7: Move singletons to app.state [CODE-MED-3]
- **Files**: `gateway/core/database.py`, `gateway/core/redis.py`, `gateway/main.py`
- **Fix**: Move engine/session factory and Redis client into `app.state` during lifespan. Remove global statements and `reset_*()` functions.
- **Tests (1)**: Two concurrent app instances don't share state.

### Task 8: Refactor lifespan function [CODE-MED-4]
- **Files**: `gateway/main.py`
- **Fix**: Extract `_init_bittensor()`, `_shutdown_services()`. Consolidate ADAPTER_DEFINITIONS into single loop.
- **Tests (0)**: Existing lifespan tests cover this.

### Task 9: Add `_is_safe_ip` edge case tests [TEST-MED-1]
- **Files**: New tests in `tests/routing/test_selector.py`
- **Fix**: Test-only.
- **Tests (1)**: Parametrized test with ~10 IP/expected pairs.

### Task 10: Add HSTS production mode test [TEST-MED-2]
- **Files**: `tests/middleware/test_security_headers.py`
- **Fix**: Test-only.
- **Tests (1)**: Verify HSTS header present when `debug=False`.

---

## Phase 3: LOW Severity (7 tasks, ~5 new tests)

### Task 11: Clarify score sampling logic [CODE-LOW-1]
- **Files**: `gateway/subnets/base.py`
- **Fix**: Move sampling entirely into `_record_score`, remove `response_complete` param for success calls.
- **Tests (1)**: Verify observation respects sample rate.

### Task 12: Improve rate limit return type [CODE-LOW-2]
- **Files**: `gateway/core/rate_limit.py`, `gateway/api/auth.py`
- **Fix**: Return `SimpleRateLimitResult` dataclass instead of `int | None` with sentinel `-1`.
- **Tests (0)**: Existing tests cover behavior.

### Task 13: Extract header name constants [CODE-LOW-3]
- **Files**: New `gateway/core/constants.py`, update 5 files
- **Fix**: Define `HEADER_MINER_UID`, `HEADER_LATENCY_MS`, `HEADER_SUBNET` constants.
- **Tests (0)**: Pure rename.

### Task 14: Use monotonic clock for staleness [PERF-LOW-1]
- **Files**: `gateway/routing/metagraph_sync.py`
- **Fix**: Add `last_sync_monotonic` for staleness, keep `last_sync_wall` for display.
- **Tests (1)**: Mock time.time() jump, verify staleness uses monotonic.

### Task 15: Optimize sensitive key pattern matching [PERF-LOW-2]
- **Files**: `gateway/core/logging.py`
- **Fix**: Pre-compile patterns into single regex.
- **Tests (0)**: Existing tests cover redaction.

### Task 16: Reduce miner selection log level [CODE-LOW-4]
- **Files**: `gateway/routing/selector.py`
- **Fix**: Change `logger.info(...)` to `logger.debug(...)` for `miner_selected`.
- **Tests (0)**: No test needed.

### Task 17: Consolidate test helpers [CODE-LOW-5]
- **Files**: `tests/conftest.py`, `tests/api/test_chat.py`, `tests/api/test_code.py`, `tests/api/test_images.py`
- **Fix**: Move `_get_api_key` to shared conftest fixture.
- **Tests (0)**: Test infrastructure cleanup.
