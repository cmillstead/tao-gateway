# Story 6.1: Admin API Endpoints

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want API endpoints that expose system-wide metrics and health data,
so that I can monitor gateway operations and respond to issues.

## Acceptance Criteria

1. **Given** I am authenticated with admin-level credentials
   **When** I send `GET /admin/metrics`
   **Then** I receive request volume, error rates, and average latency across all subnets (FR37)
   **And** data is broken down per subnet with configurable time range (last hour, 24h, 7d, 30d)

2. **Given** I am authenticated as admin
   **When** I send `GET /admin/metagraph`
   **Then** I receive metagraph sync status for each subnet (FR38)
   **And** each entry includes: last sync timestamp, staleness duration, sync success/failure status, number of active miners

3. **Given** I am authenticated as admin
   **When** I send `GET /admin/developers`
   **Then** I receive signup metrics: total registered developers, new signups (daily/weekly), weekly active developers (FR39)
   **And** a per-developer summary showing request counts by subnet and last active timestamp

4. **Given** I am authenticated as admin
   **When** I send `GET /admin/miners`
   **Then** I receive miner quality scores per subnet (FR40)
   **And** each entry includes: miner UID, incentive score, gateway quality score, response count, average latency, error rate

5. **Given** the admin auth model
   **When** determining if a user is an admin
   **Then** admin status is determined by an `is_admin` boolean on the organization record
   **And** this flag is set directly in the database (no self-service admin promotion)
   **And** Cevin's account is seeded as admin during initial setup

6. **Given** I am not authenticated or authenticated as a regular developer
   **When** I attempt to access any `/admin/*` endpoint
   **Then** I receive a 401 or 403 response
   **And** admin endpoints are not discoverable in the public OpenAPI docs

## Tasks / Subtasks

- [x] Task 1: Add `is_admin` column to Organization model (AC: #5)
  - [x]1.1 Add `is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")` to `Organization` model in `gateway/models/organization.py`
  - [x]1.2 Generate Alembic migration: `uv run alembic revision --autogenerate -m "add is_admin to organizations"`
  - [x]1.3 Run and verify migration: `uv run alembic upgrade head`

- [x] Task 2: Create admin auth dependency (AC: #5, #6)
  - [x]2.1 Create `require_admin` dependency in `gateway/middleware/auth.py` that wraps `get_current_org_id()` and checks `Organization.is_admin == True` in the DB
  - [x]2.2 Return `uuid.UUID` (org_id) on success, raise `AuthorizationError` (403) if not admin
  - [x]2.3 Add `AuthorizationError` to `gateway/core/exceptions.py` if it doesn't exist — a distinct exception from `AuthenticationError` (401 vs 403)
  - [x]2.4 Register `AuthorizationError` → 403 mapping in `gateway/middleware/error_handler.py`

- [x] Task 3: Create admin Pydantic schemas (AC: #1, #2, #3, #4)
  - [x]3.1 Create `gateway/schemas/admin.py` with the following response models:
  - [x]3.2 `SubnetMetrics`: `subnet_name: str`, `netuid: int`, `request_count: int`, `success_count: int`, `error_count: int`, `error_rate: float`, `avg_latency_ms: float`, `p50_latency_ms: int`, `p95_latency_ms: int`, `p99_latency_ms: int`
  - [x]3.3 `MetricsResponse`: `time_range: str`, `subnets: list[SubnetMetrics]`, `total_requests: int`, `total_errors: int`, `overall_error_rate: float`
  - [x]3.4 `SubnetMetagraphStatus`: `netuid: int`, `subnet_name: str`, `last_sync_time: str | None`, `staleness_seconds: float`, `is_stale: bool`, `sync_status: Literal["healthy", "degraded", "never_synced"]`, `last_sync_error: str | None`, `consecutive_failures: int`, `active_miners: int`
  - [x]3.5 `MetagraphResponse`: `subnets: list[SubnetMetagraphStatus]`
  - [x]3.6 `DeveloperSummary`: `org_id: str`, `email: str`, `signup_date: str`, `last_active: str | None`, `total_requests: int`, `requests_by_subnet: dict[str, int]`
  - [x]3.7 `DeveloperMetrics`: `total_developers: int`, `new_signups_today: int`, `new_signups_this_week: int`, `weekly_active_developers: int`, `developers: list[DeveloperSummary]`
  - [x]3.8 `MinerInfo`: `miner_uid: int`, `hotkey: str`, `netuid: int`, `subnet_name: str`, `incentive_score: float`, `gateway_quality_score: float`, `total_requests: int`, `successful_requests: int`, `avg_latency_ms: float`, `error_rate: float`
  - [x]3.9 `MinerResponse`: `subnets: dict[str, list[MinerInfo]]` — keyed by subnet name

- [x] Task 4: Create admin service layer (AC: #1, #3)
  - [x]4.1 Create `gateway/services/admin_service.py`
  - [x]4.2 `get_system_metrics(db, time_range)` — cross-org aggregation of usage data:
    - For completed days: query `DailyUsageSummary` without `org_id` filter, grouped by `netuid`/`subnet_name`
    - For today: query `UsageRecord` without `org_id` filter
    - Compute error rates: `error_count / request_count`
    - Time range mapping: `"1h"` → last hour from `UsageRecord`, `"24h"` → today, `"7d"` → last 7 days, `"30d"` → last 30 days
  - [x]4.3 `get_developer_metrics(db)` — query `organizations` table:
    - Total count, new signups today/this week (from `created_at`), weekly active (orgs with any `UsageRecord` in last 7 days)
    - Per-developer: join `Organization` with `UsageRecord` aggregated by `subnet_name`, get `MAX(created_at)` as last active
  - [x]4.4 Note: metagraph and miner data come from `app.state` objects, not the DB, so no service methods needed for those

- [x] Task 5: Create admin API endpoints (AC: #1, #2, #3, #4, #6)
  - [x]5.1 Create `gateway/api/admin.py` with `router = APIRouter()`
  - [x]5.2 `GET /admin/metrics` — accepts `time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$")`. Calls `admin_service.get_system_metrics()`. Returns `MetricsResponse`.
  - [x]5.3 `GET /admin/metagraph` — reads from `request.app.state.metagraph_manager.get_all_states()`. Converts `SubnetMetagraphState` to `SubnetMetagraphStatus` schema. For `active_miners`: count neurons with non-zero incentive from metagraph object. Returns `MetagraphResponse`.
  - [x]5.4 `GET /admin/developers` — calls `admin_service.get_developer_metrics()`. Returns `DeveloperMetrics`.
  - [x]5.5 `GET /admin/miners` — reads live data from `request.app.state.scorer` (in-memory `_MinerState` via the scorer's internal state). Also reads persisted `MinerScore` from DB for historical context. For incentive scores: read from metagraph object via `metagraph_manager`. Returns `MinerResponse`.
  - [x]5.6 All endpoints use `Depends(require_admin)` for auth
  - [x]5.7 Exclude admin router from default OpenAPI schema: use `include_in_schema=False` on the router or individual endpoints

- [x] Task 6: Register admin router (AC: #6)
  - [x]6.1 Import admin router in `gateway/api/router.py`
  - [x]6.2 Add `router.include_router(admin_router, prefix="/admin", tags=["Admin"])` — but with `include_in_schema=False` so admin endpoints are hidden from public `/docs`

- [x] Task 7: Write tests (AC: all)
  - [x]7.1 Test `is_admin` column exists on Organization model and defaults to False
  - [x]7.2 Test `require_admin` dependency: returns org_id for admin user, raises 403 for non-admin, raises 401 for unauthenticated
  - [x]7.3 Test `GET /admin/metrics` returns per-subnet metrics with correct aggregation for each time range
  - [x]7.4 Test `GET /admin/metrics` with different `time_range` query params
  - [x]7.5 Test `GET /admin/metagraph` returns subnet sync status (use mock metagraph manager in app.state)
  - [x]7.6 Test `GET /admin/developers` returns correct signup and activity counts
  - [x]7.7 Test `GET /admin/miners` returns miner quality data (use mock scorer in app.state)
  - [x]7.8 Test all admin endpoints return 401 without auth and 403 for non-admin users
  - [x]7.9 Test admin endpoints are NOT included in OpenAPI schema (`GET /openapi.json` should not contain `/admin/*` paths)
  - [x]7.10 Verify all existing tests still pass: `uv run pytest --tb=short -q`

## Dev Notes

### Architecture Patterns and Constraints

- **Backend-only story** — no dashboard UI changes (that's Story 6.2)
- **No TypeScript client regeneration needed** — admin endpoints are excluded from OpenAPI schema, so the dashboard client is unaffected
- **SQLAlchemy 2.x async** — all DB operations use `async with session` pattern. Models use `Mapped[]` type annotations with `mapped_column()`.
- **structlog for all logging** — never use `print()` or stdlib `logging`. Use `structlog.get_logger()`.
- **Pydantic v2 schemas** — all request/response models use Pydantic v2 `BaseModel`. Separate from SQLAlchemy models.
- **Service boundary** — API routes call service functions, service functions call DB models. Routes never query DB directly.
- **Admin auth is JWT-based** — same as dashboard auth (`get_current_org_id()`), plus an `is_admin` check. NOT API key auth.
- **Metagraph and scorer data come from `app.state`** — these are in-memory objects set during FastAPI lifespan. Access via `request.app.state.metagraph_manager` and `request.app.state.scorer`. No DB queries needed for these.
- **Error response envelope** — all errors use the standard error format: `{"error": {"type": "...", "message": "...", "code": N}}`

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| `Organization` model | EXISTS, needs `is_admin` column | `gateway/models/organization.py` |
| `get_current_org_id()` | EXISTS (JWT auth for dashboard) | `gateway/middleware/auth.py` |
| `get_usage_summaries()` | EXISTS (org-scoped) | `gateway/services/usage_service.py` |
| `DailyUsageSummary` model | EXISTS | `gateway/models/daily_usage_summary.py` |
| `UsageRecord` model | EXISTS | `gateway/models/usage_record.py` |
| `MinerScorer` class | EXISTS (in-memory EMA scoring) | `gateway/routing/scorer.py` |
| `MinerScore` DB model | EXISTS (persisted snapshots) | `gateway/models/miner_score.py` |
| `MetagraphManager` class | EXISTS | `gateway/routing/metagraph_sync.py` |
| `SubnetMetagraphState` dataclass | EXISTS | `gateway/routing/metagraph_sync.py` |
| `GatewayError` exception hierarchy | EXISTS | `gateway/core/exceptions.py` |
| `error_handler` middleware | EXISTS | `gateway/middleware/error_handler.py` |
| `gateway/api/admin.py` | DOES NOT EXIST | — |
| `gateway/schemas/admin.py` | DOES NOT EXIST | — |
| `gateway/services/admin_service.py` | DOES NOT EXIST | — |
| `require_admin` dependency | DOES NOT EXIST | — |
| `AuthorizationError` exception | DOES NOT EXIST (check first) | — |
| `is_admin` on Organization | DOES NOT EXIST | — |

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/middleware/auth.py` → `get_current_org_id()`** — WRAP this for admin auth. Do not create a separate JWT validation mechanism.
- **`gateway/services/usage_service.py` → `get_usage_summaries()`** — USE as reference for query patterns. The admin version removes the `org_id` filter and aggregates across all orgs.
- **`gateway/models/daily_usage_summary.py`** — QUERY this for completed-day metrics (cross-org). Fields: `netuid`, `subnet_name`, `summary_date`, `request_count`, `success_count`, `error_count`, `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms`.
- **`gateway/models/usage_record.py`** — QUERY this for live/today data and for "last hour" metrics. Fields: `org_id`, `netuid`, `subnet_name`, `latency_ms`, `status_code`, `created_at`.
- **`gateway/routing/scorer.py` → `MinerScorer`** — READ scores via `get_scores(netuid)` for live quality data. For richer data (request counts, avg latency), access `_states` dict via a new public method or use the DB `MinerScore` model for last-flushed snapshots.
- **`gateway/routing/metagraph_sync.py` → `MetagraphManager.get_all_states()`** — READ this for metagraph status. Returns `dict[int, SubnetMetagraphState]` with `last_sync_time`, `is_stale`, `last_sync_error`, `consecutive_failures`, plus the `metagraph` object for neuron counts.
- **`gateway/schemas/health.py`** — REFERENCE for response schema patterns (SubnetHealthStatus, HealthResponse).
- **`gateway/api/health.py`** — REFERENCE for accessing `app.state` objects from route handlers.
- **`gateway/core/exceptions.py`** — ADD `AuthorizationError` here if not already present. Follow existing `GatewayError` hierarchy.
- **`gateway/middleware/error_handler.py`** — ADD 403 mapping for `AuthorizationError`.

### What NOT to Touch

- Do NOT modify existing usage query functions in `usage_service.py` — create new cross-org functions in `admin_service.py`
- Do NOT modify the `MinerScorer` internals — read from it via its public API or the DB model
- Do NOT modify the `MetagraphManager` — read from it via `get_all_states()`
- Do NOT add dashboard UI — that's Story 6.2
- Do NOT add alerting or notifications — that's Phase 2
- Do NOT modify rate limiting behavior
- Do NOT expose admin endpoints in the public OpenAPI schema

### API Endpoint Design

**GET /admin/metrics?time_range=24h**
```json
{
  "time_range": "24h",
  "total_requests": 1247,
  "total_errors": 23,
  "overall_error_rate": 0.018,
  "subnets": [
    {
      "subnet_name": "sn1",
      "netuid": 1,
      "request_count": 800,
      "success_count": 785,
      "error_count": 15,
      "error_rate": 0.019,
      "avg_latency_ms": 342.5,
      "p50_latency_ms": 280,
      "p95_latency_ms": 650,
      "p99_latency_ms": 1200
    }
  ]
}
```

**GET /admin/metagraph**
```json
{
  "subnets": [
    {
      "netuid": 1,
      "subnet_name": "sn1",
      "last_sync_time": "2026-03-14T12:00:00Z",
      "staleness_seconds": 45.2,
      "is_stale": false,
      "sync_status": "healthy",
      "last_sync_error": null,
      "consecutive_failures": 0,
      "active_miners": 128
    }
  ]
}
```

**GET /admin/developers**
```json
{
  "total_developers": 47,
  "new_signups_today": 3,
  "new_signups_this_week": 12,
  "weekly_active_developers": 18,
  "developers": [
    {
      "org_id": "uuid",
      "email": "dev@example.com",
      "signup_date": "2026-03-01T00:00:00Z",
      "last_active": "2026-03-14T11:30:00Z",
      "total_requests": 542,
      "requests_by_subnet": {"sn1": 400, "sn19": 100, "sn62": 42}
    }
  ]
}
```

**GET /admin/miners?netuid=1** (optional filter)
```json
{
  "subnets": {
    "sn1": [
      {
        "miner_uid": 42,
        "hotkey": "5F3sa2...",
        "netuid": 1,
        "subnet_name": "sn1",
        "incentive_score": 0.0234,
        "gateway_quality_score": 0.87,
        "total_requests": 156,
        "successful_requests": 150,
        "avg_latency_ms": 340.2,
        "error_rate": 0.038
      }
    ]
  }
}
```

### Admin Auth Design

```python
async def require_admin(
    request: Request,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Validate that the authenticated user is an admin."""
    org = await db.scalar(
        select(Organization).where(Organization.id == org_id)
    )
    if org is None or not org.is_admin:
        raise AuthorizationError("Admin access required")
    return org_id
```

### Miner Data Strategy

The `/admin/miners` endpoint needs data from two sources:
1. **Live in-memory scores** from `MinerScorer` (`app.state.scorer`) — EMA quality score, request counts since last flush, avg latency
2. **Incentive scores** from metagraph objects (`app.state.metagraph_manager`) — `metagraph.I[uid]` gives the incentive score per neuron

The `MinerScorer.get_scores()` returns only `dict[str, float]` (hotkey → quality_score). For richer data, add a new public method `get_all_miner_states(netuid)` that returns full `_MinerState` data (or read from the DB `MinerScore` model for last-flushed snapshots).

**Recommended approach:** Add a `get_miner_details(netuid)` method to `MinerScorer` that returns `list[MinerQualityScore]` without resetting counters (unlike `get_snapshot_and_reset()`). This avoids exposing internal `_MinerState` and doesn't interfere with the score flush cycle.

### Metrics Time Range Implementation

| Time Range | Data Source | Query Strategy |
|---|---|---|
| `1h` | `UsageRecord` | `WHERE created_at >= now() - interval '1 hour'`, group by `netuid` |
| `24h` | `DailyUsageSummary` (yesterday) + `UsageRecord` (today) | Same pattern as `get_usage_summaries()` but cross-org |
| `7d` | `DailyUsageSummary` (last 6 days) + `UsageRecord` (today) | Cross-org aggregation |
| `30d` | `DailyUsageSummary` (last 29 days) + `UsageRecord` (today) | Cross-org aggregation |

For latency percentiles in the `1h` window, use `percentile_cont()` on live `UsageRecord` rows (same approach as `usage_service.py` lines 111-118).

### OpenAPI Schema Exclusion

To hide admin endpoints from `/docs`:
```python
# In gateway/api/admin.py
router = APIRouter()

# Option A: Per-endpoint (most explicit)
@router.get("/metrics", include_in_schema=False)

# Option B: When mounting in router.py
router.include_router(admin_router, prefix="/admin", tags=["Admin"], include_in_schema=False)
```

Option B is cleaner — one line hides all admin endpoints.

### Project Structure Notes

New files:
```
gateway/
├── api/
│   └── admin.py                     # Admin API endpoints (4 routes)
├── schemas/
│   └── admin.py                     # Admin response schemas
├── services/
│   └── admin_service.py             # Cross-org metrics and developer queries
migrations/versions/
│   └── xxxx_add_is_admin_to_organizations.py  # Alembic migration
```

Modified files:
```
gateway/
├── models/organization.py           # Add is_admin column
├── middleware/auth.py               # Add require_admin dependency
├── core/exceptions.py              # Add AuthorizationError (if not present)
├── middleware/error_handler.py      # Add 403 mapping
├── api/router.py                   # Register admin router
```

### Testing Standards

- **Use real Postgres and Redis** — no mocking DB or cache (per CLAUDE.md)
- **Mock only Bittensor SDK** — external service that's impractical to run locally
- **For metagraph/scorer tests:** Create test instances of `MetagraphManager` and `MinerScorer` and set them on `app.state` in test fixtures. Do NOT mock these — use real instances with test data.
- **Test file locations**: `tests/api/test_admin.py` (all admin endpoint tests), `tests/middleware/test_auth_middleware.py` (extend with admin auth tests)
- **Admin test fixture**: Create a helper to set `is_admin=True` on a test org, or create a dedicated admin org in `conftest.py`
- **After completion**: Run `uv run pytest --tb=short -q`, `uv run ruff check gateway/ tests/`, `uv run mypy gateway/`

### Previous Story Intelligence (Story 5.3)

- **550 backend tests pass** — this story should not break any
- **Branch naming**: `feat/story-6.1-admin-api-endpoints`
- **Commit messages**: `feat: add <description> (Story 6.1)`
- **Code review patterns from 5.3**: Expect scrutiny on error handling consistency, type safety, removal of dead code, shared helper extraction
- **Redis cache format**: `key_hash:key_id:org_id:debug_mode` — no changes needed for this story
- **CORS**: `PATCH` was added to allowed methods in Story 5.3 — no CORS changes needed for admin (GET only, same-origin)

### Git Intelligence (Recent Commits)

- `faab268` feat: add per-key debug mode with content logging and 48h cleanup (Story 5.3) (#37)
- `f60454c` feat: add usage dashboard with Recharts charts, quota display, and code quality fixes (Story 5.2) (#36)
- Pattern: feature branches merged via PR with squash
- Expected branch: `feat/story-6.1-admin-api-endpoints`

### Security Considerations

- **Admin auth must be robust** — a compromised admin endpoint exposes all developer data, system metrics, and miner details
- **Email exposure** — the `/admin/developers` endpoint returns developer emails. This is acceptable for the sole operator (Cevin), but if admin access expands later, consider email masking
- **No rate limiting on admin endpoints** — acceptable for MVP with single admin user. If multiple admins are added, consider rate limiting.
- **403 vs 401**: Return 401 for unauthenticated (no/invalid JWT), 403 for authenticated but not admin. This distinction matters for clients.
- **Do NOT log full developer emails** in structlog output — log only the domain or a hash if needed for debugging

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6, Story 6.1]
- [Source: _bmad-output/planning-artifacts/prd.md#FR37 — Operator: request volume, error rates, latency]
- [Source: _bmad-output/planning-artifacts/prd.md#FR38 — Operator: metagraph sync status]
- [Source: _bmad-output/planning-artifacts/prd.md#FR39 — Operator: signup and activity metrics]
- [Source: _bmad-output/planning-artifacts/prd.md#FR40 — Operator: miner quality scores]
- [Source: _bmad-output/planning-artifacts/architecture.md#API Boundaries — /admin/* require admin-level auth]
- [Source: _bmad-output/planning-artifacts/architecture.md#Service Boundaries]
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication & Security — JWT httpOnly cookies for dashboard]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — gateway/api/admin.py (FR37-40)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Requirements to Structure Mapping — FR37-40 → api/admin.py]
- [Source: _bmad-output/planning-artifacts/architecture.md#Error handling — Global exception handler with typed exceptions]
- [Source: gateway/models/organization.py — Organization model, needs is_admin column]
- [Source: gateway/middleware/auth.py — get_current_org_id(), JWT auth for dashboard]
- [Source: gateway/services/usage_service.py — get_usage_summaries() reference pattern for cross-org version]
- [Source: gateway/models/daily_usage_summary.py — DailyUsageSummary model for metrics queries]
- [Source: gateway/models/usage_record.py — UsageRecord model for live data queries]
- [Source: gateway/routing/scorer.py — MinerScorer.get_scores(), needs get_miner_details()]
- [Source: gateway/routing/metagraph_sync.py — MetagraphManager.get_all_states() for sync status]
- [Source: gateway/models/miner_score.py — MinerScore DB model for persisted snapshots]
- [Source: gateway/core/exceptions.py — GatewayError hierarchy, add AuthorizationError]
- [Source: gateway/middleware/error_handler.py — Global exception → HTTP response mapping]
- [Source: gateway/api/router.py — Router mounting pattern]
- [Source: gateway/api/health.py — Reference for accessing app.state from routes]
- [Source: _bmad-output/implementation-artifacts/5-3-debug-mode-and-content-cleanup.md — Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- All 7 tasks completed: is_admin column, admin auth dependency, schemas, service layer, API endpoints, router registration, tests
- 17 new admin tests + 1 updated model test = 571 total tests passing
- Alembic migration generated for is_admin column
- Added `get_miner_details()` method to MinerScorer for non-destructive read of miner data
- Admin endpoints hidden from OpenAPI schema via `include_in_schema=False`
- AuthorizationError (403) added to exception hierarchy
- Linter (ruff) and type checker (mypy) pass clean

### Change Log

- 2026-03-14: Story 6.1 implemented — admin API endpoints for system metrics, metagraph status, developer activity, and miner quality
- 2026-03-14: Code review fixes — N+1 query eliminated in developer metrics (H1), float("inf") staleness fixed (H2), sync error sanitized (M1), added unit tests for get_miner_details (M2), added multi-subnet + netuid filter tests (M3/L3), consolidated TYPE_CHECKING blocks + removed unused logger (L1/L2)

### File List

New files:
- gateway/api/admin.py
- gateway/schemas/admin.py
- gateway/services/admin_service.py
- migrations/versions/3a75e60c89a1_add_is_admin_to_organizations.py
- tests/api/test_admin.py

Modified files:
- gateway/models/organization.py (added is_admin column)
- gateway/middleware/auth.py (added require_admin dependency, AuthorizationError import)
- gateway/core/exceptions.py (added AuthorizationError class)
- gateway/api/router.py (registered admin router with include_in_schema=False)
- gateway/routing/scorer.py (added get_miner_details method)
- tests/models/test_models.py (updated organization columns assertion)
