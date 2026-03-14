# Story 5.1: Usage Metering & Storage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want my request activity recorded and queryable,
so that I can understand my usage patterns and access historical data via the API.

## Acceptance Criteria

1. **Given** I send any request to a subnet endpoint (SN1, SN19, SN62)
   **When** the response is returned (any status code)
   **Then** the usage middleware asynchronously writes a usage record with: API key ID, org ID, subnet name, netuid, endpoint path, miner UID, latency_ms, status code, token count (prompt + completion + total), and timestamp
   **And** the write does not add latency to the response (fire-and-forget via `asyncio.create_task`)
   **And** no request or response content is included in the record (FR41 — metadata only)

2. **Given** usage records accumulate over time
   **When** the database stores them
   **Then** the `usage_records` table uses monthly partitioning via PostgreSQL table inheritance or declarative partitioning (NFR17)
   **And** detailed records are retained for 90 days
   **And** the schema supports efficient queries by api_key_id, netuid, and time range (composite indexes)

3. **Given** the daily aggregation background task fires (once per day)
   **When** it processes the previous day's detailed records
   **Then** it generates daily summaries per key, per subnet in a `daily_usage_summaries` table: request_count, success_count, error_count, p50_latency_ms, p95_latency_ms, p99_latency_ms, total_prompt_tokens, total_completion_tokens
   **And** aggregated summaries are retained indefinitely (NFR27)

4. **Given** a developer calls `GET /v1/usage`
   **When** they provide a valid API key (bearer token auth)
   **Then** the response returns per-subnet usage data for the authenticated key's org: request counts, latency percentiles, token totals, and remaining quota
   **And** the response supports optional query params: `subnet` (filter), `start_date`, `end_date` (ISO 8601), `granularity` (daily/monthly, default daily)
   **And** data comes from `daily_usage_summaries` for completed days and live `usage_records` for today

5. **Given** a developer calls `GET /dashboard/usage`
   **When** they are authenticated via JWT cookie
   **Then** the response returns the same data as `/v1/usage` but scoped to the dashboard user's org
   **And** includes quota information per subnet (monthly limit from rate limiter, current month usage count)

## Tasks / Subtasks

- [x] Task 1: Create `usage_records` table and model (AC: #1, #2)
  - [x] 1.1 Create `gateway/models/usage_record.py` with SQLAlchemy model: `id` (UUID PK), `api_key_id` (UUID FK → api_keys.id), `org_id` (UUID FK → organizations.id), `subnet_name` (str), `netuid` (int), `endpoint` (str), `miner_uid` (str, nullable), `latency_ms` (int), `status_code` (int), `prompt_tokens` (int, default 0), `completion_tokens` (int, default 0), `total_tokens` (int, default 0), `created_at` (timestamptz, default now)
  - [x] 1.2 Add composite index: `ix_usage_records_api_key_id_created_at` on (api_key_id, created_at)
  - [x] 1.3 Add composite index: `ix_usage_records_org_id_netuid_created_at` on (org_id, netuid, created_at)
  - [x] 1.4 Add index: `ix_usage_records_created_at` on (created_at) for aggregation queries and retention cleanup
  - [x] 1.5 Register model in `gateway/models/__init__.py`
  - [x] 1.6 Create Alembic migration for the table

- [x] Task 2: Create `daily_usage_summaries` table and model (AC: #3)
  - [x] 2.1 Create `gateway/models/daily_usage_summary.py`: `id` (UUID PK), `org_id` (UUID FK), `api_key_id` (UUID FK), `netuid` (int), `subnet_name` (str), `summary_date` (date), `request_count` (int), `success_count` (int), `error_count` (int), `p50_latency_ms` (int), `p95_latency_ms` (int), `p99_latency_ms` (int), `total_prompt_tokens` (bigint), `total_completion_tokens` (bigint), `created_at` (timestamptz)
  - [x] 2.2 Add unique constraint: `uq_daily_usage_summaries_key_subnet_date` on (api_key_id, netuid, summary_date)
  - [x] 2.3 Add composite index: `ix_daily_usage_summaries_org_id_netuid_date` on (org_id, netuid, summary_date)
  - [x] 2.4 Register model in `gateway/models/__init__.py`
  - [x] 2.5 Create Alembic migration for the table

- [x] Task 3: Create usage middleware (AC: #1)
  - [x] 3.1 Create `gateway/middleware/usage.py` with a `record_usage` async function that writes a `UsageRecord` to DB
  - [x] 3.2 The function takes: `api_key_id`, `org_id`, `subnet_name`, `netuid`, `endpoint`, `miner_uid`, `latency_ms`, `status_code`, `prompt_tokens`, `completion_tokens`, `total_tokens`
  - [x] 3.3 Uses `asyncio.create_task` for fire-and-forget writes — must NOT add latency to the response
  - [x] 3.4 Uses its own `async_sessionmaker` session (NOT the request session) to avoid transaction conflicts
  - [x] 3.5 Catches and logs all exceptions (never crash the request path)
  - [x] 3.6 Uses structlog with keyword args (never f-strings)

- [x] Task 4: Integrate usage recording into subnet endpoints (AC: #1)
  - [x] 4.1 In `gateway/api/chat.py`: after `adapter.execute()` returns, call `record_usage()` via `asyncio.create_task` with response metadata
  - [x] 4.2 In `gateway/api/images.py`: same pattern
  - [x] 4.3 In `gateway/api/code.py`: same pattern
  - [x] 4.4 For streaming responses (`chat.py` stream path): record usage after stream completes (in the generator's finally block or after the generator is consumed)
  - [x] 4.5 For error responses (GatewayError caught in endpoint): still record usage with the error status code and available metadata (miner_uid may be null)
  - [x] 4.6 Token counts: use values from the adapter response where available (SN1 has `usage` field); default to 0 for SN19/SN62

- [x] Task 5: Create usage Pydantic schemas (AC: #4, #5)
  - [x] 5.1 Create `gateway/schemas/usage.py` with: `UsageSummary` (request_count, success_count, error_count, p50/p95/p99 latency, token totals), `SubnetUsage` (subnet_name, netuid, summaries list, quota info), `UsageResponse` (list of SubnetUsage, period info)
  - [x] 5.2 Add query params schema: `UsageQueryParams` (subnet: Optional[str], start_date: Optional[date], end_date: Optional[date], granularity: Literal["daily", "monthly"] = "daily")
  - [x] 5.3 Add `DashboardUsageResponse` extending `UsageResponse` with per-subnet quota (monthly_limit, monthly_used, monthly_remaining)

- [x] Task 6: Create usage service (AC: #4, #5)
  - [x] 6.1 Create `gateway/services/usage_service.py` with `get_usage()` — queries `daily_usage_summaries` for completed days, falls back to `usage_records` for current day
  - [x] 6.2 Add `get_quota_status()` — reads monthly rate limit counts from `_SUBNET_RATE_LIMITS` config and current month's usage from `daily_usage_summaries` + today's `usage_records`
  - [x] 6.3 Support date range filtering and subnet filtering
  - [x] 6.4 Support monthly granularity by aggregating daily summaries

- [x] Task 7: Create API routes (AC: #4, #5)
  - [x] 7.1 Create `gateway/api/usage.py` with `GET /v1/usage` — bearer token auth via `get_current_api_key`, calls usage service, returns `UsageResponse`
  - [x] 7.2 Add `GET /dashboard/usage` to `gateway/api/dashboard.py` — JWT cookie auth, calls usage service + quota, returns `DashboardUsageResponse`
  - [x] 7.3 Register routes in `gateway/api/router.py`

- [x] Task 8: Create daily aggregation background task (AC: #3)
  - [x] 8.1 Create `gateway/tasks/usage_aggregation.py` following `ScoreFlushTask` pattern (start/stop lifecycle, asyncio.create_task loop)
  - [x] 8.2 Task runs once per day (configurable interval, default 86400s)
  - [x] 8.3 Aggregates previous day's `usage_records` into `daily_usage_summaries` using SQL: COUNT, percentile_cont for p50/p95/p99, SUM for tokens
  - [x] 8.4 Uses `pg_insert` with `ON CONFLICT DO UPDATE` on the unique constraint (idempotent re-runs)
  - [x] 8.5 Add retention cleanup: delete `usage_records` older than 90 days
  - [x] 8.6 Register task in `gateway/main.py` lifespan (start on startup, stop on shutdown)
  - [x] 8.7 Add config settings: `usage_aggregation_interval_seconds` (default 86400), `usage_retention_days` (default 90)

- [x] Task 9: Write tests (AC: all)
  - [x] 9.1 `tests/models/test_usage_models.py` — model creation, constraints, indexes
  - [x] 9.2 `tests/middleware/test_usage_middleware.py` — record_usage writes to DB, fire-and-forget doesn't block, exception handling
  - [x] 9.3 `tests/services/test_usage_service.py` — get_usage with date ranges, subnet filters, granularity; get_quota_status
  - [x] 9.4 `tests/api/test_usage.py` — GET /v1/usage (bearer auth), GET /dashboard/usage (JWT auth), query params, empty state
  - [x] 9.5 `tests/tasks/test_usage_aggregation.py` — aggregation produces correct summaries, percentile calculation, idempotent re-runs, retention cleanup
  - [x] 9.6 Integration: verify subnet endpoint calls trigger usage recording (check DB after request)
  - [x] 9.7 All existing tests still pass (511+ tests)

## Dev Notes

### Architecture Patterns and Constraints

- **Fire-and-forget usage writes are MANDATORY** — usage recording must NEVER add latency to API responses. Use `asyncio.create_task(record_usage(...))` after the response is ready. The task must use its own DB session (not the request session).
- **No request/response content in usage records** — FR41 mandates metadata-only logging by default. Debug content logging is Story 5.3's scope. Do NOT add content fields to `usage_records`.
- **Monthly partitioning** — NFR17 requires time-based partitioning. For MVP, use PostgreSQL declarative partitioning (`PARTITION BY RANGE (created_at)`) or simpler approach: partition management via the aggregation task creating monthly child tables. Alternatively, since MVP scale is low (5,000 req/day), a single table with the `ix_usage_records_created_at` index is acceptable — add a TODO comment for partitioning at scale.
- **Dual auth for usage endpoints** — `GET /v1/usage` uses bearer token auth (existing `get_current_api_key` dependency). `GET /dashboard/usage` uses JWT cookie auth (existing `get_current_org` dependency in `gateway/api/dashboard.py`).
- **Quota = monthly rate limit** — Free tier quotas are the monthly rate limits in `_SUBNET_RATE_LIMITS` (rate_limit.py line 37-43): SN1=1000/mo, SN19=500/mo, SN62=1000/mo. Quota status = monthly_limit - current_month_usage_count.
- **Daily aggregation follows ScoreFlushTask pattern** — see `gateway/tasks/score_flush.py` for the exact lifecycle pattern: `__init__`, `start()`, `stop()`, `_loop()`, `flush_once()`. Register in `gateway/main.py` lifespan alongside `score_flush_task`.
- **Percentile calculation** — Use PostgreSQL's `percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)` for p50/p95/p99 in the aggregation query. This is a standard PostgreSQL aggregate function.

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| `usage_records` table | Does NOT exist | — |
| `daily_usage_summaries` table | Does NOT exist | — |
| `gateway/models/usage_record.py` | Does NOT exist | — |
| `gateway/models/daily_usage_summary.py` | Does NOT exist | — |
| `gateway/middleware/usage.py` | Does NOT exist | — |
| `gateway/services/usage_service.py` | Does NOT exist | — |
| `gateway/api/usage.py` | Does NOT exist | — |
| `gateway/schemas/usage.py` | Does NOT exist | — |
| `gateway/tasks/usage_aggregation.py` | Does NOT exist | — |
| `gateway/tasks/score_flush.py` | EXISTS — reference pattern for background tasks | `gateway/tasks/score_flush.py` |
| `gateway/middleware/rate_limit.py` | EXISTS — has `_SUBNET_RATE_LIMITS` with monthly quotas | `gateway/middleware/rate_limit.py:37-43` |
| `gateway/api/dashboard.py` | EXISTS — has `GET /dashboard/overview` | `gateway/api/dashboard.py` |
| `gateway/api/router.py` | EXISTS — registers all routes | `gateway/api/router.py` |
| `gateway/core/config.py` | EXISTS — Settings class, needs new config fields | `gateway/core/config.py` |
| `gateway/main.py` | EXISTS — lifespan manages background tasks | `gateway/main.py` |
| Token counts in SN1 | Hardcoded to 0 | `gateway/subnets/sn1_text.py:79-83` |
| Subnet endpoint handlers | EXISTS — need usage recording integration | `gateway/api/chat.py`, `images.py`, `code.py` |

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/tasks/score_flush.py`** — COPY this pattern exactly for `UsageAggregationTask`. Same lifecycle: `__init__` with session_factory, `start()`/`stop()` with asyncio.create_task, `_loop()` with sleep, `flush_once()` with guarded exception handling.
- **`gateway/main.py` lifespan (lines 120-133)** — Follow exact same pattern to create and register `UsageAggregationTask`. Start after `score_flush_task.start()`, stop before `score_flush_task.stop()`.
- **`gateway/middleware/auth.py`** — `get_current_api_key` returns `ApiKeyInfo(key_id, org_id, prefix)`. Use `key_id` and `org_id` for usage records.
- **`gateway/middleware/rate_limit.py`** — `_SUBNET_RATE_LIMITS` (line 37-43) and `get_subnet_rate_limits()` provide monthly quota limits. Import and use for quota calculation.
- **`gateway/api/dashboard.py`** — Has `get_current_org` dependency for JWT auth. Add the `GET /dashboard/usage` route here.
- **`gateway/models/base.py`** — `Base` (DeclarativeBase) and `TimestampMixin` (created_at, updated_at). Use `Base` for new models. `TimestampMixin` adds both created_at and updated_at — usage_records only needs created_at, so define it directly instead of using the mixin.
- **`gateway/core/database.py`** — `get_session_factory()` returns `async_sessionmaker[AsyncSession]`. Use for the usage middleware's own session and the aggregation task.
- **`gateway/schemas/dashboard.py`** — `OverviewResponse` model. Reference for Pydantic schema patterns in this project.

### What NOT to Touch

- Do NOT modify `gateway/subnets/base.py` — usage recording happens at the endpoint handler level, not in the adapter
- Do NOT modify `gateway/middleware/rate_limit.py` — quota info is read-only from `_SUBNET_RATE_LIMITS`
- Do NOT modify `gateway/middleware/auth.py` — existing auth dependencies work as-is
- Do NOT add debug content logging — that's Story 5.3's scope
- Do NOT add Recharts or dashboard UI components — that's Story 5.2's scope
- Do NOT modify existing UI components in `dashboard/src/` — this story is backend only
- Do NOT add billing/payment logic — deferred to Phase 2
- Do NOT modify the SN1 token count behavior (hardcoded 0) — correct token counting is a separate concern; record whatever the adapter provides

### Usage Recording Integration Pattern

```python
# In each subnet endpoint handler (chat.py, images.py, code.py):
import asyncio
from gateway.middleware.usage import record_usage

# After successful response:
response_data, headers = await adapter.execute(...)
asyncio.create_task(record_usage(
    session_factory=get_session_factory(),
    api_key_id=api_key.key_id,
    org_id=api_key.org_id,
    subnet_name=config.subnet_name,
    netuid=config.netuid,
    endpoint=request.url.path,
    miner_uid=headers.get("X-TaoGateway-Miner-UID"),
    latency_ms=int(headers.get("X-TaoGateway-Latency-Ms", 0)),
    status_code=200,
    prompt_tokens=response_data.get("usage", {}).get("prompt_tokens", 0),
    completion_tokens=response_data.get("usage", {}).get("completion_tokens", 0),
    total_tokens=response_data.get("usage", {}).get("total_tokens", 0),
))

# After error (in except block):
asyncio.create_task(record_usage(
    session_factory=get_session_factory(),
    api_key_id=api_key.key_id,
    org_id=api_key.org_id,
    subnet_name=config.subnet_name,
    netuid=config.netuid,
    endpoint=request.url.path,
    miner_uid=None,  # may not have selected a miner
    latency_ms=elapsed_ms,
    status_code=exc.status_code,  # from GatewayError
    prompt_tokens=0,
    completion_tokens=0,
    total_tokens=0,
))
```

### Aggregation Task SQL Pattern

```sql
-- Daily aggregation query (run via SQLAlchemy)
INSERT INTO daily_usage_summaries (
    org_id, api_key_id, netuid, subnet_name, summary_date,
    request_count, success_count, error_count,
    p50_latency_ms, p95_latency_ms, p99_latency_ms,
    total_prompt_tokens, total_completion_tokens
)
SELECT
    org_id, api_key_id, netuid, subnet_name,
    DATE(created_at) as summary_date,
    COUNT(*) as request_count,
    COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 400) as success_count,
    COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) as p50_latency_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99_latency_ms,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(completion_tokens) as total_completion_tokens
FROM usage_records
WHERE created_at >= :start_of_day AND created_at < :end_of_day
GROUP BY org_id, api_key_id, netuid, subnet_name, DATE(created_at)
ON CONFLICT ON CONSTRAINT uq_daily_usage_summaries_key_subnet_date
DO UPDATE SET
    request_count = EXCLUDED.request_count,
    success_count = EXCLUDED.success_count,
    error_count = EXCLUDED.error_count,
    p50_latency_ms = EXCLUDED.p50_latency_ms,
    p95_latency_ms = EXCLUDED.p95_latency_ms,
    p99_latency_ms = EXCLUDED.p99_latency_ms,
    total_prompt_tokens = EXCLUDED.total_prompt_tokens,
    total_completion_tokens = EXCLUDED.total_completion_tokens;
```

### Project Structure Notes

New files:
```
gateway/
├── models/
│   ├── usage_record.py              # UsageRecord SQLAlchemy model
│   └── daily_usage_summary.py       # DailyUsageSummary SQLAlchemy model
├── schemas/
│   └── usage.py                     # Usage response Pydantic schemas
├── middleware/
│   └── usage.py                     # record_usage() fire-and-forget function
├── services/
│   └── usage_service.py             # get_usage(), get_quota_status()
├── api/
│   └── usage.py                     # GET /v1/usage route
└── tasks/
    └── usage_aggregation.py         # UsageAggregationTask background task

migrations/versions/
└── xxxx_add_usage_records_and_summaries.py  # Alembic migration

tests/
├── models/
│   └── test_usage_models.py
├── middleware/
│   └── test_usage_middleware.py
├── services/
│   └── test_usage_service.py
├── api/
│   └── test_usage.py
└── tasks/
    └── test_usage_aggregation.py
```

Modified files:
- `gateway/models/__init__.py` — add UsageRecord, DailyUsageSummary
- `gateway/api/router.py` — register usage routes
- `gateway/api/dashboard.py` — add GET /dashboard/usage
- `gateway/api/chat.py` — add usage recording after response
- `gateway/api/images.py` — add usage recording after response
- `gateway/api/code.py` — add usage recording after response
- `gateway/core/config.py` — add usage_aggregation_interval_seconds, usage_retention_days
- `gateway/main.py` — register UsageAggregationTask in lifespan

### Testing Standards

- **Real Postgres and Redis** — use Docker test containers, never mock DB
- **Mock only Bittensor SDK** — everything else uses real infrastructure
- Run backend: `uv run pytest --tb=short -q`
- Lint: `uv run ruff check gateway/ tests/`
- Types: `uv run mypy gateway/`
- **511 backend tests currently pass** — this story must not break any existing tests
- **Test the fire-and-forget pattern** — use `await asyncio.sleep(0.1)` in tests to let the background task complete, then check DB
- **Test aggregation with real percentile calculations** — insert known latency values, verify p50/p95/p99 match expected values
- **Test idempotent aggregation** — run aggregation twice for the same day, verify summaries are unchanged

### Previous Story Intelligence (Story 4.4)

- **511 backend tests pass** — baseline for regression testing
- **openapi-fetch client introduced** — `dashboard/src/api/client.ts` is the typed API client. Story 5.2 (dashboard usage page) will use it to call the new `/dashboard/usage` endpoint. This story only creates the backend; no frontend changes.
- **`scripts/generate_api_client.sh`** — after adding new endpoints, regenerate the TypeScript client so Story 5.2 gets typed access for free. Run this as a final step.
- **f-string anti-pattern in structlog** — NEVER use f-strings in structlog calls; use keyword args: `logger.info("usage_recorded", api_key_id=key_id, subnet=subnet_name)` NOT `logger.info(f"Recorded usage for {key_id}")`
- **Pattern: `credentials: "include"`** — all dashboard fetch calls use cookie auth. Backend `/dashboard/usage` must return proper CORS and cookie headers (already handled by existing middleware).
- **Code review patterns from 4.2/4.3/4.4:** Expect scrutiny on: error handling consistency, type safety, removal of dead code, shared helper extraction.
- **conftest.py `_clean_state`** — autouse fixture truncates ALL tables between tests. New `usage_records` and `daily_usage_summaries` tables will be auto-cleaned because they inherit from `Base` (already covered by `_create_tables` fixture that drops/recreates from `Base.metadata`).

### Git Intelligence (Recent Commits)

- `257b7fa` feat: add typed API client generation with openapi-fetch (Story 4.4) (#34)
- `992dee1` feat: add account overview dashboard (Story 4.3) (#33)
- `deaba2d` feat: add API key management dashboard (Story 4.2) (#32)
- `24cc47f` Merge PR #31: Story 4.1 dashboard shell and auth
- Pattern: feature branches merged via PR. Expected branch: `feat/story-5.1-usage-metering-and-storage`
- Pattern: commit messages follow `feat: add <description> (Story X.Y)`
- Pattern: PRs include all backend tests passing + ruff + mypy clean

### Security Considerations

- **No new sensitive data exposure** — usage records contain metadata only (key IDs, latency, status codes, token counts). No request/response content (FR41).
- **Auth boundaries** — `/v1/usage` requires bearer token (API key auth), `/dashboard/usage` requires JWT cookie (dashboard auth). Each endpoint sees only the authenticated user's org data.
- **No cross-org data leakage** — usage queries MUST filter by `org_id` from the authenticated context. Never allow key_id-only filtering without org_id verification.
- **UUID primary keys** — usage records use UUID PKs (not sequential integers) to prevent enumeration.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5, Story 5.1]
- [Source: _bmad-output/planning-artifacts/prd.md#Usage Monitoring — FR17, FR18, FR19, FR20]
- [Source: _bmad-output/planning-artifacts/prd.md#Data Privacy — FR41, FR42]
- [Source: _bmad-output/planning-artifacts/prd.md#Scalability — NFR17 (partitioning)]
- [Source: _bmad-output/planning-artifacts/prd.md#Data Retention — NFR27 (indefinite summaries)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Architecture — "Usage records: Async append to Postgres, monthly partitions"]
- [Source: _bmad-output/planning-artifacts/architecture.md#Background Tasks — "usage_aggregation.py: Daily usage rollups"]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — gateway/tasks/usage_aggregation.py, gateway/middleware/usage.py, gateway/services/usage_service.py]
- [Source: gateway/tasks/score_flush.py — reference background task pattern]
- [Source: gateway/middleware/rate_limit.py:37-43 — _SUBNET_RATE_LIMITS with monthly quotas]
- [Source: gateway/api/chat.py — subnet endpoint handler pattern for usage integration]
- [Source: gateway/api/dashboard.py — dashboard route pattern with JWT auth]
- [Source: _bmad-output/implementation-artifacts/4-4-api-client-generation-and-dashboard-build-pipeline.md — previous story dev notes]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Created `UsageRecord` model with UUID PK, FK constraints, and 3 composite indexes. Alembic migration generated and applied.
- Task 2: Created `DailyUsageSummary` model with unique constraint on (api_key_id, netuid, summary_date). Alembic migration included in same file.
- Task 3: Created `record_usage()` fire-and-forget function using own session factory, with exception handling that never crashes the request path.
- Task 4: Integrated usage recording into all 3 subnet endpoints (chat, images, code) — success and error paths. Streaming records in finally block. Passed `api_key` through to helper functions with None-guard.
- Task 5: Created Pydantic v2 schemas: `UsageSummary`, `SubnetUsage`, `UsageResponse`, `SubnetQuota`, `SubnetUsageWithQuota`, `DashboardUsageResponse`, `UsageQueryParams`.
- Task 6: Created `usage_service.py` with `get_usage_summaries()` (queries summaries + live records for today) and `get_quota_status()` (reads monthly limits from rate_limit config).
- Task 7: Created `GET /v1/usage` (bearer auth) and `GET /dashboard/usage` (JWT auth) routes. Registered in router.
- Task 8: Created `UsageAggregationTask` following ScoreFlushTask pattern. Registered in main.py lifespan. Added config settings.
- Task 9: 23 new tests across 5 test files. 534 total tests pass. Ruff clean. Mypy clean.

### Change Log

- 2026-03-14: Story 5.1 implementation complete — usage metering, storage, aggregation, and API endpoints
- 2026-03-14: Code review #1 — 6 issues fixed (2 HIGH, 4 MEDIUM): added quota to GET /v1/usage (AC #4 compliance), validated granularity param with Literal["daily", "monthly"], added usage recording for generic exceptions in chat.py, added elapsed time tracking for streaming, removed dead UsageQueryParams schema, added integration test for usage recording

### File List

New files:
- gateway/models/usage_record.py — UsageRecord SQLAlchemy model
- gateway/models/daily_usage_summary.py — DailyUsageSummary SQLAlchemy model
- gateway/schemas/usage.py — Pydantic v2 schemas for usage responses
- gateway/middleware/usage.py — record_usage() fire-and-forget function
- gateway/services/usage_service.py — get_usage_summaries(), get_quota_status()
- gateway/api/usage.py — GET /v1/usage route
- gateway/tasks/usage_aggregation.py — UsageAggregationTask background task
- migrations/versions/6dfa0ac14cca_add_usage_records_and_daily_usage_.py — Alembic migration
- tests/models/test_usage_models.py — 5 tests
- tests/middleware/test_usage_middleware.py — 3 tests
- tests/services/test_usage_service.py — 6 tests
- tests/api/test_usage.py — 8 tests
- tests/tasks/test_usage_aggregation.py — 4 tests

Modified files:
- gateway/models/__init__.py — added UsageRecord, DailyUsageSummary exports
- gateway/api/router.py — registered usage_router
- gateway/api/dashboard.py — added GET /dashboard/usage endpoint
- gateway/api/chat.py — added usage recording (success + error + streaming paths)
- gateway/api/images.py — added usage recording (success + error paths)
- gateway/api/code.py — added usage recording (success + error paths)
- gateway/core/config.py — added usage_aggregation_interval_seconds, usage_retention_days
- gateway/main.py — registered UsageAggregationTask in lifespan (start + shutdown)
