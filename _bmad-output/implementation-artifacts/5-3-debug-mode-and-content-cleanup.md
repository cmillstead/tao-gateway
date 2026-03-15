# Story 5.3: Debug Mode & Content Cleanup

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to temporarily enable debug logging for my API key,
so that I can troubleshoot issues by reviewing my recent request and response content.

## Acceptance Criteria

1. **Given** I am logged in to the dashboard
   **When** I enable debug mode for a specific API key
   **Then** subsequent requests using that key store request and response content alongside the metadata record (FR27)
   **And** debug mode is scoped to the individual key — other keys are unaffected

2. **Given** debug mode is enabled for my key
   **When** I send a request
   **Then** the request body and response body are stored in a `debug_logs` table with the usage record reference
   **And** a 48-hour TTL is set on each debug entry

3. **Given** the debug cleanup background task fires
   **When** it scans the `debug_logs` table
   **Then** all entries older than 48 hours are permanently deleted (FR42)
   **And** the deletion is logged as a structured event (count of records purged)

4. **Given** debug mode is enabled
   **When** I view my recent requests in the dashboard (or via API)
   **Then** I can see the full request and response content for debug-enabled requests
   **And** entries older than 48h are no longer available

5. **Given** the privacy policy
   **When** debug content is stored
   **Then** content is never associated with user identity for analytics
   **And** content is never used for quality scoring (scoring remains in-memory per FR43)

## Tasks / Subtasks

- [x] Task 1: Add `debug_mode` column to API keys and create `debug_logs` table (AC: #1, #2)
  - [x]1.1 Add `debug_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")` to `ApiKey` model in `gateway/models/api_key.py`
  - [x]1.2 Create `gateway/models/debug_log.py` with model: `id` (UUID PK), `usage_record_id` (UUID FK → usage_records.id), `api_key_id` (UUID FK → api_keys.id, indexed), `request_body` (Text, nullable), `response_body` (Text, nullable), `created_at` (DateTime with timezone, server_default=func.now(), indexed)
  - [x]1.3 Register `DebugLog` in `gateway/models/__init__.py`
  - [x]1.4 Generate Alembic migration: `uv run alembic revision --autogenerate -m "add debug_mode to api_keys and debug_logs table"`
  - [x]1.5 Run and verify migration: `uv run alembic upgrade head`
  - [x]1.6 Add index on `debug_logs.created_at` for efficient TTL cleanup queries
  - [x]1.7 Add composite index on `debug_logs(api_key_id, created_at DESC)` for efficient per-key debug log listing

- [x] Task 2: Add `debug_mode` to auth middleware `ApiKeyInfo` (AC: #1)
  - [x]2.1 Add `debug_mode: bool` field to `ApiKeyInfo` dataclass in `gateway/middleware/auth.py`
  - [x]2.2 Populate `debug_mode` from the API key record during authentication (the key is already loaded from DB/cache)
  - [x]2.3 If using Redis key cache: ensure `debug_mode` is included in the cached key info; update cache serialization/deserialization
  - [x]2.4 Update any tests that construct `ApiKeyInfo` to include `debug_mode=False`

- [x] Task 3: Modify usage middleware to capture debug content (AC: #2)
  - [x]3.1 Add optional parameters to `record_usage()` in `gateway/middleware/usage.py`: `debug_mode: bool = False`, `request_body: str | None = None`, `response_body: str | None = None`
  - [x]3.2 Inside `record_usage()`, after creating `UsageRecord`, check if `debug_mode is True` and content is available
  - [x]3.3 If debug mode: create a `DebugLog` entry with `usage_record_id`, `api_key_id`, `request_body`, `response_body`
  - [x]3.4 Commit both records in the same session transaction
  - [x]3.5 Truncate request/response bodies to a reasonable max size (e.g., 64KB each) to prevent abuse

- [x] Task 4: Pass debug content from subnet endpoints (AC: #2)
  - [x]4.1 In `gateway/api/chat.py`: capture `request.model_dump_json()` before calling adapter, capture response body after adapter returns. Pass to `record_usage()` along with `debug_mode` from `api_key_info.debug_mode`
  - [x]4.2 In `gateway/api/images.py`: same pattern — capture request/response content, pass to `record_usage()`
  - [x]4.3 In `gateway/api/code.py`: same pattern
  - [x]4.4 Only serialize content if `api_key_info.debug_mode is True` — do NOT serialize request/response bodies when debug mode is off (avoid unnecessary serialization overhead)

- [x] Task 5: Create debug log cleanup background task (AC: #3)
  - [x]5.1 Create `gateway/tasks/debug_cleanup.py` following `ScoreFlushTask`/`UsageAggregationTask` pattern
  - [x]5.2 Class `DebugLogCleanupTask` with `__init__(session_factory, cleanup_interval_seconds, retention_hours=48)`
  - [x]5.3 `cleanup_once()` method: `DELETE FROM debug_logs WHERE created_at < now() - interval '48 hours'`; log count of deleted records via structlog
  - [x]5.4 `start()`/`stop()` lifecycle methods matching existing task pattern
  - [x]5.5 Add config settings to `gateway/core/config.py`: `debug_log_cleanup_interval_seconds: int = 3600` (hourly), `debug_log_retention_hours: int = 48`
  - [x]5.6 Start task in `gateway/main.py` lifespan alongside `UsageAggregationTask`

- [x] Task 6: Add backend API endpoints for debug mode (AC: #1, #4)
  - [x]6.1 Add `PATCH /dashboard/api-keys/{key_id}` endpoint in `gateway/api/api_keys.py` — accepts `ApiKeyUpdateRequest(debug_mode: bool)`, returns updated key info
  - [x]6.2 Add `GET /dashboard/api-keys/{key_id}/debug-logs` endpoint — returns paginated debug log entries for the specified key, filtered by the requesting org's ownership
  - [x]6.3 Create schemas in `gateway/schemas/api_keys.py`: `ApiKeyUpdateRequest`, `DebugLogEntry` (id, usage_record_id, request_body, response_body, created_at), `DebugLogListResponse` (items, total)
  - [x]6.4 Add `debug_mode: bool` to `ApiKeyListItem` and `ApiKeyCreateResponse` schemas
  - [x]6.5 Add service methods in `gateway/services/api_key_service.py`: `update_api_key(session, key_id, org_id, updates)`, `get_debug_logs(session, key_id, org_id, limit, offset)`
  - [x]6.6 Ensure org ownership validation: developer can only toggle debug mode / view debug logs for their own keys

- [x] Task 7: Regenerate TypeScript API client and add types (AC: #1, #4)
  - [x]7.1 Export OpenAPI schema and regenerate `dashboard/src/api/schema.d.ts` (same process as Story 5.2: run Python to export schema, then `npx openapi-typescript`)
  - [x]7.2 Add new type re-exports to `dashboard/src/types/index.ts`: `ApiKeyUpdateRequest`, `DebugLogEntry`, `DebugLogListResponse`

- [x] Task 8: Add dashboard UI for debug mode toggle (AC: #1)
  - [x]8.1 Add `useUpdateApiKey()` mutation hook in `dashboard/src/hooks/useApiKeys.ts` — PATCH `/dashboard/api-keys/{key_id}` with `{ debug_mode: boolean }`, invalidates API keys query on success
  - [x]8.2 Add debug mode toggle to `ApiKeyTable.tsx` — a switch/toggle in the Actions column (only for active keys). Show "Debug" label. On toggle, call `useUpdateApiKey()`.
  - [x]8.3 Add "Debug" status indicator in the table — show a subtle badge or icon when debug mode is active for a key
  - [x]8.4 Consider a confirmation dialog for enabling debug mode (since it stores content temporarily)

- [x] Task 9: Add dashboard UI for viewing debug logs (AC: #4)
  - [x]9.1 Create `dashboard/src/hooks/useDebugLogs.ts` — TanStack Query hook for `GET /dashboard/api-keys/{key_id}/debug-logs` with pagination params
  - [x]9.2 Create `dashboard/src/components/api-keys/DebugLogViewer.tsx` — expandable/collapsible panel or dialog showing recent debug log entries for a key
  - [x]9.3 Each log entry shows: timestamp, request body (in a code block/pre), response body (in a code block/pre)
  - [x]9.4 Add "View Debug Logs" button in `ApiKeyTable.tsx` actions — only visible when key has debug mode enabled
  - [x]9.5 Empty state: "No debug logs yet. Send a request with this key to see content here."
  - [x]9.6 Show 48h TTL notice: "Debug logs are automatically deleted after 48 hours."

- [x] Task 10: Write tests (AC: all)
  - [x]10.1 Test `debug_mode` column exists on API key model and defaults to False
  - [x]10.2 Test `DebugLog` model creation with all fields
  - [x]10.3 Test `record_usage()` creates `DebugLog` when `debug_mode=True` and content provided
  - [x]10.4 Test `record_usage()` does NOT create `DebugLog` when `debug_mode=False`
  - [x]10.5 Test `DebugLogCleanupTask.cleanup_once()` deletes entries older than 48h and leaves newer ones
  - [x]10.6 Test `PATCH /dashboard/api-keys/{key_id}` toggles debug mode
  - [x]10.7 Test `GET /dashboard/api-keys/{key_id}/debug-logs` returns only logs for the requesting org's keys
  - [x]10.8 Test `GET /dashboard/api-keys/{key_id}/debug-logs` returns empty list for key belonging to another org
  - [x]10.9 Test debug content is truncated at max size limit
  - [x]10.10 Verify all existing tests still pass: `uv run pytest --tb=short -q`

## Dev Notes

### Architecture Patterns and Constraints

- **This is a full-stack story** — backend model + migration + middleware + API endpoints + background task + frontend UI
- **SQLAlchemy 2.x async** — all DB operations use `async with session` pattern. Models use `Mapped[]` type annotations with `mapped_column()`.
- **structlog for all logging** — never use `print()` or stdlib `logging`. Use `structlog.get_logger()`. Log debug cleanup counts as structured events.
- **Background task pattern** — follow `ScoreFlushTask`/`UsageAggregationTask` exactly: `__init__`, `start()`, `stop()`, `_loop()` with `asyncio.sleep()`. Register in `main.py` lifespan.
- **Fire-and-forget usage recording** — `record_usage()` is called via `asyncio.create_task()`. The debug log creation happens inside this same function.
- **Auth middleware carries key info** — `ApiKeyInfo` dataclass is populated during auth and available via `Depends(require_api_key)` in subnet endpoints. Adding `debug_mode` here avoids a second DB lookup per request.
- **Redis key cache** — the auth middleware caches key info in Redis with 60s TTL. The cached data must include `debug_mode`. When debug mode is toggled, the cache entry for that key's prefix should be invalidated.
- **Content size limits** — truncate request/response bodies to 64KB each to prevent storage abuse. Log a warning if content is truncated.
- **Privacy** — debug content is never used for analytics, quality scoring, or any purpose other than developer troubleshooting. Content is deleted after 48h automatically.

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| `ApiKey` model | EXISTS, needs `debug_mode` column | `gateway/models/api_key.py` |
| `ApiKeyInfo` dataclass | EXISTS, needs `debug_mode` field | `gateway/middleware/auth.py` |
| `record_usage()` function | EXISTS, needs debug content params | `gateway/middleware/usage.py` |
| `ScoreFlushTask` | EXISTS (reference pattern) | `gateway/tasks/score_flush.py` |
| `UsageAggregationTask` | EXISTS (reference pattern) | `gateway/tasks/usage_aggregation.py` |
| `PATCH /dashboard/api-keys/{key_id}` | DOES NOT EXIST | — |
| `GET /dashboard/api-keys/{key_id}/debug-logs` | DOES NOT EXIST | — |
| `debug_logs` table | DOES NOT EXIST | — |
| `DebugLog` model | DOES NOT EXIST | — |
| `DebugLogCleanupTask` | DOES NOT EXIST | — |
| `debug_cleanup.py` task file | DOES NOT EXIST | `gateway/tasks/` |
| Debug mode toggle in dashboard | DOES NOT EXIST | — |
| Debug log viewer in dashboard | DOES NOT EXIST | — |

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/models/usage_record.py`** — COPY this model pattern for `DebugLog`. Same UUID PK pattern, same `created_at` column, same FK pattern.
- **`gateway/tasks/usage_aggregation.py`** — COPY this task pattern for `DebugLogCleanupTask`. Same `start()`/`stop()`/`_loop()` lifecycle.
- **`gateway/middleware/usage.py`** — EXTEND `record_usage()` with debug params. Do not create a separate function.
- **`gateway/middleware/auth.py`** — EXTEND `ApiKeyInfo` dataclass. Do not create a new auth mechanism.
- **`gateway/api/api_keys.py`** — ADD endpoints here. Follow existing patterns for org ownership validation.
- **`gateway/schemas/api_keys.py`** — ADD new schemas here. Follow existing Pydantic v2 patterns.
- **`gateway/services/api_key_service.py`** — ADD service methods here. Follow existing `async def` pattern with session parameter.
- **`dashboard/src/hooks/useApiKeys.ts`** — ADD new hooks here. Follow `useRotateApiKey()`/`useRevokeApiKey()` mutation patterns.
- **`dashboard/src/components/api-keys/ApiKeyTable.tsx`** — ADD debug toggle and debug log viewer button to the existing Actions column.
- **`dashboard/src/components/ui/`** — USE shadcn/ui primitives: `switch` (for toggle), `dialog` (for debug log viewer), `badge` (for debug status), `button`, `card`.
- **`dashboard/src/api/client.ts`** — USE the typed openapi-fetch client for all API calls.
- **`dashboard/src/lib/utils.ts`** — USE `cn()` for Tailwind class merging.

### What NOT to Touch

- Do NOT modify the `UsageRecord` model — debug content goes in a separate `debug_logs` table
- Do NOT modify the `DailyUsageSummary` model — aggregation is unrelated to debug content
- Do NOT modify `gateway/api/dashboard.py` — usage/overview endpoints are separate scope
- Do NOT add billing features — Phase 2
- Do NOT add admin-level debug viewing — that's Epic 6 scope
- Do NOT persist debug content beyond 48 hours under any circumstances
- Do NOT use debug content for quality scoring (FR43)
- Do NOT change the existing rate limiting behavior — debug mode only affects content logging

### API Endpoint Design

**PATCH /dashboard/api-keys/{key_id}**
```json
// Request
{ "debug_mode": true }

// Response (same as ApiKeyListItem with debug_mode)
{
  "id": "uuid",
  "prefix": "tao_sk_live_abc...",
  "name": "My Key",
  "is_active": true,
  "debug_mode": true,
  "created_at": "2026-03-14T00:00:00Z"
}
```

**GET /dashboard/api-keys/{key_id}/debug-logs?limit=20&offset=0**
```json
{
  "items": [
    {
      "id": "uuid",
      "usage_record_id": "uuid",
      "request_body": "{\"model\": \"sn1\", \"messages\": [...]}",
      "response_body": "{\"choices\": [...]}",
      "created_at": "2026-03-14T12:00:00Z"
    }
  ],
  "total": 42
}
```

### Database Schema — debug_logs Table

```sql
CREATE TABLE debug_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usage_record_id UUID NOT NULL REFERENCES usage_records(id),
    api_key_id UUID NOT NULL REFERENCES api_keys(id),
    request_body TEXT,
    response_body TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_debug_logs_api_key_id_created_at ON debug_logs(api_key_id, created_at DESC);
CREATE INDEX ix_debug_logs_created_at ON debug_logs(created_at);
```

### Redis Cache Invalidation

When debug mode is toggled via PATCH endpoint:
1. Update `debug_mode` in Postgres
2. Delete the Redis cache entry for that key's prefix (key format: check `gateway/middleware/auth.py` for the cache key pattern)
3. Next request with that key will re-populate the cache with the updated `debug_mode` value

### Content Serialization Strategy

- **Request body**: Serialize the Pydantic request model to JSON string via `.model_dump_json()`
- **Response body**: Serialize the response before returning — use `.model_dump_json()` on the Pydantic response model
- **Only serialize when `debug_mode is True`** — check `api_key_info.debug_mode` before any serialization to avoid overhead on non-debug requests
- **Truncate at 64KB** — if serialized content exceeds 64KB, truncate and append `\n... [truncated at 64KB]`

### Project Structure Notes

New files:
```
gateway/
├── models/
│   └── debug_log.py                    # DebugLog SQLAlchemy model
├── tasks/
│   └── debug_cleanup.py                # DebugLogCleanupTask background task
dashboard/src/
├── hooks/
│   └── useDebugLogs.ts                 # TanStack Query hook for debug logs
├── components/
│   └── api-keys/
│       └── DebugLogViewer.tsx           # Debug log viewer dialog/panel
```

Modified files:
```
gateway/
├── models/__init__.py                   # Register DebugLog
├── models/api_key.py                    # Add debug_mode column
├── middleware/auth.py                   # Add debug_mode to ApiKeyInfo
├── middleware/usage.py                  # Add debug content params to record_usage()
├── api/api_keys.py                     # Add PATCH and debug-logs GET endpoints
├── api/chat.py                         # Pass debug content to record_usage()
├── api/images.py                       # Pass debug content to record_usage()
├── api/code.py                         # Pass debug content to record_usage()
├── schemas/api_keys.py                 # Add debug_mode, DebugLogEntry, etc.
├── services/api_key_service.py         # Add update_api_key, get_debug_logs
├── core/config.py                      # Add debug cleanup config settings
├── main.py                             # Start DebugLogCleanupTask
migrations/versions/                    # New migration file
dashboard/src/
├── api/schema.d.ts                     # Regenerated with new endpoints/types
├── types/index.ts                      # Add debug type re-exports
├── hooks/useApiKeys.ts                 # Add useUpdateApiKey mutation
├── components/api-keys/ApiKeyTable.tsx  # Add debug toggle + debug logs button
```

### Testing Standards

- **Use real Postgres and Redis** — no mocking DB or cache (per CLAUDE.md)
- **Mock only Bittensor SDK** — external service that's impractical to run locally
- **Test file locations**: `tests/models/test_debug_log.py`, `tests/tasks/test_debug_cleanup.py`, `tests/api/test_api_keys.py` (extend existing), `tests/middleware/test_usage_middleware.py` (extend existing)
- **After completion**: Run `uv run pytest --tb=short -q`, `uv run ruff check gateway/ tests/`, `uv run mypy gateway/`
- **Frontend**: Regenerate API client, run `npm run build` in dashboard directory

### Previous Story Intelligence (Story 5.2)

- **536 backend tests pass** — this story should not break any
- **TypeScript schema regeneration**: Export OpenAPI schema via Python script, then `npx openapi-typescript`. Does NOT require running backend server.
- **Shared constants pattern**: Story 5.2 extracted shared subnet constants to `subnet-constants.ts`. Follow this pattern if shared constants are needed.
- **Code review patterns**: Expect scrutiny on error handling consistency, type safety, removal of dead code, shared helper extraction.
- **shadcn/ui switch component**: May not be installed yet. If not, install via `npx shadcn@latest add switch` in dashboard directory.

### Git Intelligence (Recent Commits)

- `f60454c` feat: add usage dashboard (Story 5.2) (#36)
- `d83289a` Merge PR #35: Story 5.1
- Pattern: feature branches merged via PR. Expected branch: `feat/story-5.3-debug-mode-and-content-cleanup`
- Pattern: commit messages follow `feat: add <description> (Story X.Y)`

### Security Considerations

- **Debug content is sensitive** — request/response bodies may contain user-generated content, PII, or business logic. The 48h TTL ensures it doesn't persist.
- **Org ownership validation** — developers can only enable debug mode for their own keys, and only view debug logs for their own keys. Every endpoint must validate `org_id` ownership.
- **Content size limits** — 64KB truncation prevents storage DoS. Log a warning when content is truncated.
- **No content in logs** — debug content bodies must NEVER appear in structlog output. Only log metadata (key prefix, record count, etc.)
- **Redis cache update** — when debug mode changes, invalidate the cached key to prevent stale `debug_mode` values

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5, Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md#FR27 — Per-key debug mode]
- [Source: _bmad-output/planning-artifacts/prd.md#FR41 — Metadata only by default]
- [Source: _bmad-output/planning-artifacts/prd.md#FR42 — Auto-delete debug content after 48h]
- [Source: _bmad-output/planning-artifacts/prd.md#FR43 — Quality scores in-memory, no content persistence]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Privacy — 48h debug content TTL]
- [Source: _bmad-output/planning-artifacts/architecture.md#Background Tasks — asyncio lifespan tasks]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — gateway/tasks/debug_cleanup.py]
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication & Security]
- [Source: gateway/models/api_key.py — ApiKey model, needs debug_mode column]
- [Source: gateway/models/usage_record.py — UsageRecord model reference for DebugLog]
- [Source: gateway/middleware/auth.py — ApiKeyInfo dataclass, needs debug_mode field]
- [Source: gateway/middleware/usage.py — record_usage() function, needs debug content params]
- [Source: gateway/tasks/usage_aggregation.py — UsageAggregationTask reference pattern]
- [Source: gateway/tasks/score_flush.py — ScoreFlushTask reference pattern]
- [Source: gateway/api/api_keys.py — existing key management endpoints]
- [Source: gateway/schemas/api_keys.py — existing key schemas]
- [Source: gateway/services/api_key_service.py — existing key service methods]
- [Source: gateway/core/config.py — Settings class for new config values]
- [Source: gateway/main.py — lifespan for task registration]
- [Source: _bmad-output/implementation-artifacts/5-2-usage-dashboard-and-quota-display.md — previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Added `debug_mode` boolean column to `api_keys` table, created `debug_logs` table with FK to usage_records and api_keys, composite indexes for efficient queries. Alembic migration generated and applied.
- Task 2: Added `debug_mode: bool` field to `ApiKeyInfo` dataclass. Updated Redis cache format from `hash:key_id:org_id` to `hash:key_id:org_id:debug_mode` with backward compatibility for old cache entries. Populated from DB record during auth.
- Task 3: Extended `record_usage()` with `debug_mode`, `request_body`, `response_body` params. Creates `DebugLog` entry in same transaction when debug mode is on. Added 64KB truncation with `_truncate_content()` helper.
- Task 4: Updated chat.py, images.py, code.py to pass debug content to `record_usage()`. Content is only serialized when `api_key_info.debug_mode is True`.
- Task 5: Created `DebugLogCleanupTask` following existing task pattern. Deletes debug_logs older than 48h. Added config settings `debug_log_cleanup_interval_seconds` and `debug_log_retention_hours`. Registered in main.py lifespan.
- Task 6: Added `PATCH /dashboard/api-keys/{key_id}` for debug mode toggle, `GET /dashboard/api-keys/{key_id}/debug-logs` for viewing logs. Updated schemas with `debug_mode` on `ApiKeyListItem`, added `ApiKeyUpdateRequest`, `DebugLogEntry`, `DebugLogListResponse`. Added service methods with org ownership validation. Redis cache invalidation on debug mode change. Added PATCH to CORS allowed methods.
- Task 7: Exported OpenAPI schema and regenerated `schema.d.ts`. Added type re-exports for `ApiKeyUpdateRequest`, `DebugLogEntry`, `DebugLogListResponse`.
- Task 8: Created `Switch` shadcn/ui component. Added `useUpdateApiKey()` mutation hook. Updated `ApiKeyTable.tsx` with debug mode toggle switch per key and "Debug" column.
- Task 9: Created `useDebugLogs.ts` hook, `DebugLogViewer.tsx` dialog component with request/response content display, empty state, and 48h TTL notice. Added "View Debug Logs" button (FileText icon) visible only when debug mode is on.
- Task 10: 14 new tests added (550 total, up from 536). Tests cover: model columns, debug log indexes/FKs, record_usage with/without debug mode, content truncation, cleanup task, PATCH toggle, debug logs endpoint, cross-org isolation.

### Change Log

- 2026-03-14: Story 5.3 implementation complete — debug mode toggle, content capture, 48h cleanup task, dashboard UI
- 2026-03-14: Code review #1 — 7 issues fixed (3 HIGH, 4 MEDIUM): streaming debug capture, error-path debug content, 48h TTL query filter, renamed safe_json_dumps, PATCH schema extensibility, integration test for debug log content, safe_json_dumps tests

### File List

New files:
- gateway/models/debug_log.py
- gateway/tasks/debug_cleanup.py
- dashboard/src/components/ui/switch.tsx
- dashboard/src/hooks/useDebugLogs.ts
- dashboard/src/components/api-keys/DebugLogViewer.tsx
- tests/models/test_debug_log.py
- tests/tasks/test_debug_cleanup.py
- migrations/versions/58fd8c9eff3a_add_debug_mode_to_api_keys_and_debug_.py

Modified files:
- gateway/models/api_key.py — added debug_mode column
- gateway/models/__init__.py — registered DebugLog
- gateway/middleware/auth.py — added debug_mode to ApiKeyInfo, updated cache format
- gateway/middleware/usage.py — added debug content params, truncation, DebugLog creation
- gateway/api/chat.py — pass debug content to record_usage
- gateway/api/images.py — pass debug content to record_usage
- gateway/api/code.py — pass debug content to record_usage
- gateway/api/api_keys.py — added PATCH and debug-logs GET endpoints
- gateway/schemas/api_keys.py — added debug_mode, ApiKeyUpdateRequest, DebugLogEntry, DebugLogListResponse
- gateway/services/api_key_service.py — added update_api_key, get_debug_logs
- gateway/core/config.py — added debug cleanup config settings
- gateway/main.py — started DebugLogCleanupTask, added PATCH to CORS
- dashboard/src/api/schema.d.ts — regenerated with new endpoints
- dashboard/src/types/index.ts — added debug type re-exports
- dashboard/src/hooks/useApiKeys.ts — added useUpdateApiKey mutation
- dashboard/src/components/api-keys/ApiKeyTable.tsx — added debug toggle, debug logs button
- tests/models/test_models.py — updated api_key_columns test
- tests/middleware/test_usage_middleware.py — added debug mode tests
- tests/api/test_api_keys.py — added debug mode + debug logs tests
