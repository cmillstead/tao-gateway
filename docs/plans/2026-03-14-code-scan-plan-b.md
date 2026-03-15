# Code Scan Implementation Plan — 2026-03-14b

**Total tasks**: 20 findings (0 CRIT, 2 HIGH, 7 MED, 11 LOW)
**Total new tests**: ~18
**Vault doc**: `tao-gateway Code Scan 2026-03-14b.md`

---

## Phase 1: HIGH Severity (2 tasks, ~2 new tests)

### Task 1: Extract BackgroundTask base class [CODE-HIGH-1]
- **Files**: New `gateway/tasks/base.py`, modify `gateway/tasks/score_flush.py`, `gateway/tasks/usage_aggregation.py`, `gateway/tasks/debug_cleanup.py`
- **Fix**: Extract lifecycle boilerplate (`start()`, `stop()`, `_loop()`) into base class. Subclasses implement `run_once()` and set `task_name`.
- **Tests (1)**: Unit test for base class lifecycle (start/stop/cancellation). Existing task tests should pass.

### Task 2: Extract shared usage endpoint logic [CODE-HIGH-2]
- **Files**: `gateway/services/usage_service.py`, `gateway/api/usage.py`, `gateway/api/dashboard.py`
- **Fix**: Create `get_usage_with_quotas()` in usage_service. Both endpoints delegate to it. Remove dead `UsageResponse` schema (CODE-LOW-1).
- **Tests (0)**: Existing endpoint tests cover both paths.

---

## Phase 2: MED Severity (7 tasks, ~10 new tests)

### Task 3: Add usage recording on MinerInvalidResponseError [CODE-MED-1]
- **Files**: `gateway/api/chat.py`, `gateway/api/images.py`, `gateway/api/code.py`
- **Fix**: Add `record_usage(status_code=502)` in exception handler. Include debug content if debug_mode on.
- **Tests (2)**: Trigger MinerInvalidResponseError, assert UsageRecord with 502 written. Assert DebugLog created when debug_mode on.

### Task 4: Centralize subnet metadata registry [CODE-MED-2]
- **Files**: New `gateway/core/subnets.py`, modify `gateway/services/usage_service.py`, `gateway/api/dashboard.py`, `gateway/middleware/rate_limit.py`
- **Fix**: Single canonical registry with netuid, short name, display name. All consumers import from it.
- **Tests (1)**: Assert all consumers reference same registry.

### Task 5: Extract `fire_usage_record()` helper [CODE-MED-3]
- **Files**: New helper in `gateway/middleware/usage.py`, modify `gateway/api/chat.py`, `gateway/api/images.py`, `gateway/api/code.py`
- **Fix**: Encapsulate `asyncio.create_task(record_usage(...))` pattern. Each call site becomes 1 line.
- **Tests (0)**: Existing endpoint tests cover behavior.

### Task 6: Test usage service live-today path [TEST-MED-1]
- **Files**: `tests/services/test_usage_service.py`
- **Fix**: Test-only — seed UsageRecord rows for today, verify they appear in results.
- **Tests (2)**: `test_get_usage_summaries_includes_today_live_records`, `test_get_quota_status_includes_today_records` [TEST-MED-2].

### Task 7: Test debug logs 48h retention cutoff at query time [TEST-MED-3]
- **Files**: `tests/api/test_api_keys.py`
- **Fix**: Test-only — create expired debug log, verify excluded from results.
- **Tests (1)**: `test_get_debug_logs_excludes_expired_entries`.

### Task 8: Test monthly aggregation arithmetic [TEST-MED-4]
- **Files**: `tests/services/test_usage_service.py`
- **Fix**: Test-only — pass known daily values, assert correct sums and max latencies.
- **Tests (1)**: `test_aggregate_to_monthly_sums_correctly`.

### Task 9: Remove TS hardcoded rate limits [CODE-LOW-7 — grouped here for coherence with Task 4]
- **Files**: `dashboard/src/components/usage/subnet-constants.ts`, `dashboard/src/pages/Usage.tsx`
- **Fix**: Remove `SUBNET_RATE_LIMITS`, use API data from `useOverview()` instead.
- **Tests (0)**: Manual verification.

---

## Phase 3: LOW Severity (11 tasks, ~6 new tests)

### Task 10: Remove dead `UsageResponse` schema [CODE-LOW-1]
- **Files**: `gateway/schemas/usage.py`
- **Fix**: Delete `UsageResponse` class.
- **Tests (0)**: Nothing references it.

### Task 11: Fix `collected_chunks` debug mode conditional [CODE-LOW-2]
- **Files**: `gateway/api/chat.py`
- **Fix**: Use `None` instead of `[]` for non-debug case.
- **Tests (0)**: Existing streaming tests cover both paths.

### Task 12: Remove duplicate `adapter.get_config()` calls [CODE-LOW-3]
- **Files**: `gateway/api/images.py`, `gateway/api/code.py`
- **Fix**: Remove redundant second call at line 42.
- **Tests (0)**: Existing tests cover.

### Task 13: Consolidate `org_and_key` test fixture [CODE-LOW-4]
- **Files**: `tests/conftest.py`, 5 test files
- **Fix**: Move fixture to shared conftest as factory.
- **Tests (0)**: Infrastructure improvement.

### Task 14: Extract `_today_range()` helper [CODE-LOW-5]
- **Files**: `gateway/services/usage_service.py`
- **Fix**: Extract duplicate date range calculation.
- **Tests (0)**: Readability refactor.

### Task 15: Downgrade dashboard endpoint log levels [CODE-LOW-6]
- **Files**: `gateway/api/dashboard.py`
- **Fix**: Change `logger.info()` to `logger.debug()` for `dashboard_overview_loaded` and `dashboard_usage_loaded`.
- **Tests (0)**: No test needed.

### Task 16: Improve monthly latency aggregation [CODE-LOW-8]
- **Files**: `gateway/services/usage_service.py`
- **Fix**: Use weighted average by request_count instead of `max()`.
- **Tests (1)**: Verify weighted result with known inputs (part of Task 8).

### Task 17: Fix `safe_json_dumps` false test [TEST-LOW-1]
- **Files**: `tests/middleware/test_usage_middleware.py`
- **Fix**: Replace with meaningful test or acknowledge `except` path is effectively unreachable.
- **Tests (1)**: Self-referential fix.

### Task 18: Test Redis cache invalidation on debug toggle [TEST-LOW-2]
- **Files**: `tests/api/test_api_keys.py`
- **Fix**: Pre-populate cache, toggle, assert deleted.
- **Tests (1)**: `test_update_api_key_invalidates_redis_cache`.

### Task 19: Test `_truncate_content` boundary [TEST-LOW-3]
- **Files**: `tests/middleware/test_usage_middleware.py`
- **Fix**: Test exactly-at-limit and limit+1.
- **Tests (1)**: `test_truncate_content_exact_boundary`.

### Task 20: Consolidate duplicate `_get_api_key` test helper [previous CODE-LOW-5 — grouping]
- **Files**: `tests/conftest.py`, `tests/api/test_chat.py`, `tests/api/test_code.py`, `tests/api/test_images.py`
- **Fix**: Move to shared conftest.
- **Tests (0)**: Infrastructure cleanup.
