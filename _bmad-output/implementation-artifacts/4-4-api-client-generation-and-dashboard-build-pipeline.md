# Story 4.4: API Client Generation & Dashboard Build Pipeline

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the dashboard to use a typed API client generated from the backend's OpenAPI spec,
so that the frontend stays in sync with the backend automatically.

## Acceptance Criteria

1. **Given** the FastAPI backend's OpenAPI spec
   **When** I run the client generation script (`scripts/generate_api_client.sh`)
   **Then** a fully typed TypeScript client is generated via openapi-fetch into `dashboard/src/api/client.ts`
   **And** the generated types match all backend request/response schemas

2. **Given** the dashboard is built (`npm run build` in `dashboard/`)
   **When** the FastAPI application starts
   **Then** it serves the dashboard's static files (HTML, JS, CSS) from a mounted directory
   **And** client-side routing works via a catch-all fallback to `index.html`

3. **Given** the dashboard SPA
   **When** I navigate between pages
   **Then** TanStack Query manages server state (API keys, usage data, account info)
   **And** React Context manages auth state (JWT, current user)

4. **Given** the build pipeline
   **When** the OpenAPI spec changes (new endpoints, modified schemas)
   **Then** regenerating the client reflects the changes with type errors surfacing any frontend incompatibilities
   **And** no manual type synchronization is needed

## Tasks / Subtasks

- [x] Task 1: Install openapi-fetch and openapi-typescript (AC: #1, #4)
  - [x] 1.1 Add `openapi-fetch` as a runtime dependency in `dashboard/package.json`
  - [x] 1.2 Add `openapi-typescript` as a dev dependency in `dashboard/package.json`
  - [x] 1.3 Add `"generate-api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts"` script to `package.json`

- [x] Task 2: Create `scripts/generate_api_client.sh` (AC: #1, #4)
  - [x] 2.1 Script starts the FastAPI server in background (if not already running), waits for `/openapi.json` to be available
  - [x] 2.2 Runs `npm run generate-api` inside `dashboard/` to generate `dashboard/src/api/schema.d.ts`
  - [x] 2.3 Kills the background server if it started one
  - [x] 2.4 Script is idempotent and safe to re-run
  - [x] 2.5 Make script executable (`chmod +x`)

- [x] Task 3: Create the typed API client module (AC: #1, #4)
  - [x] 3.1 Create `dashboard/src/api/client.ts` that creates an `openapi-fetch` client instance with `baseUrl` and `credentials: "include"` (cookie auth)
  - [x] 3.2 Export the client for use in hooks
  - [x] 3.3 The client should use the generated `paths` type from `schema.d.ts`

- [x] Task 4: Migrate `useApiKeys.ts` to use generated client (AC: #1, #3)
  - [x] 4.1 Replace `fetchJson` calls with typed `client.GET`, `client.POST`, `client.DELETE` calls
  - [x] 4.2 Remove manually-defined inline type assertions — rely on generated types
  - [x] 4.3 Maintain all existing functionality (list, create, rotate, revoke)
  - [x] 4.4 Keep TanStack Query wrapping (useQuery, useMutation, invalidateQueries)

- [x] Task 5: Migrate `useOverview.ts` to use generated client (AC: #1, #3)
  - [x] 5.1 Replace `fetchJson` call with typed `client.GET("/dashboard/overview")`
  - [x] 5.2 Remove manual type assertions — rely on generated types

- [x] Task 6: Migrate `useAuth.ts` to use generated client (AC: #1, #3)
  - [x] 6.1 Replace raw `fetch()` calls with typed `client.GET`, `client.POST` for `/auth/*` endpoints
  - [x] 6.2 Maintain existing auth flow (login, signup, logout, session check)
  - [x] 6.3 Handle error responses consistently via client error handling

- [x] Task 7: Clean up manual types and fetchJson (AC: #4)
  - [x] 7.1 Remove or reduce manually-defined types in `dashboard/src/types/index.ts` that are now generated — keep any types not derived from the API (e.g., pure frontend UI state types)
  - [x] 7.2 Remove `dashboard/src/lib/api.ts` (`fetchJson`) if no longer used, or keep if used for non-API fetches
  - [x] 7.3 Update any imports across components that referenced removed types

- [x] Task 8: Verify build pipeline end-to-end (AC: #2, #4)
  - [x] 8.1 Run `scripts/generate_api_client.sh` — verify `schema.d.ts` is generated
  - [x] 8.2 Run `cd dashboard && npm run build` — verify `dist/` is produced with no errors
  - [x] 8.3 Run FastAPI server — verify dashboard loads from `/assets` mount and SPA catch-all works
  - [x] 8.4 Verify TypeScript compilation catches type mismatches: change a backend schema, regenerate, confirm `tsc --noEmit` errors surface

- [x] Task 9: Write tests (AC: all)
  - [x] 9.1 Backend: Verify `GET /openapi.json` returns valid OpenAPI 3.x schema
  - [x] 9.2 Backend: All existing tests still pass (510+ tests)
  - [x] 9.3 Frontend: `tsc --noEmit` passes (type safety verification)
  - [x] 9.4 Frontend: `npm run build` succeeds
  - [x] 9.5 Manual: Run `scripts/generate_api_client.sh` and verify output

## Dev Notes

### Architecture Patterns and Constraints

- **openapi-fetch is the chosen client library** — per architecture doc. It generates typed fetch calls from the OpenAPI spec. NOT axios, NOT react-query's built-in fetch, NOT hand-rolled clients.
- **openapi-typescript generates the type definitions** — it reads `openapi.json` and outputs a `.d.ts` file with `paths`, `components`, etc.
- **Cookie-based JWT for dashboard** — all dashboard API calls use httpOnly cookies. The openapi-fetch client MUST be configured with `credentials: "include"`.
- **TanStack Query for server state** — the generated client replaces `fetchJson` as the fetch layer, but TanStack Query still wraps the calls for caching, invalidation, and loading states.
- **React Context for auth state** — the auth hook manages JWT state and login/logout flow via React Context. This doesn't change.
- **Static serving already works** — `gateway/main.py` already mounts `/assets` from `dashboard/dist/assets` and has a catch-all route for SPA routing. No backend changes needed for serving.
- **Vite dev proxy already configured** — `vite.config.ts` proxies `/auth`, `/dashboard`, `/v1`, `/docs`, `/openapi.json` to `http://localhost:8000`. No proxy changes needed.

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| openapi-fetch / openapi-typescript | NOT installed | — |
| `scripts/generate_api_client.sh` | Does NOT exist | — |
| `dashboard/src/api/` | Does NOT exist | — |
| `dashboard/src/lib/api.ts` | `fetchJson` generic wrapper | Used by `useApiKeys.ts`, `useOverview.ts` |
| `useAuth.ts` | Raw `fetch()` calls | `dashboard/src/hooks/useAuth.ts` |
| `useApiKeys.ts` | `fetchJson` + TanStack Query | `dashboard/src/hooks/useApiKeys.ts` |
| `useOverview.ts` | `fetchJson` + TanStack Query | `dashboard/src/hooks/useOverview.ts` |
| Static file serving | Working — catch-all + `/assets` mount | `gateway/main.py` lines 275-291 |
| Vite dev proxy | Working — proxies API routes | `dashboard/vite.config.ts` |
| Dashboard build | Working — `tsc -b && vite build` | `dashboard/package.json` |
| Manually-defined types | In `dashboard/src/types/index.ts` | API response types defined manually |

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/main.py` (lines 275-291)** — Static serving and SPA catch-all already implemented. Do NOT modify this.
- **`dashboard/vite.config.ts`** — Dev proxy already routes `/openapi.json` to the backend. Do NOT modify proxy config.
- **`dashboard/src/hooks/useApiKeys.ts`** — TanStack Query pattern. Migrate the fetch layer but keep the query/mutation structure.
- **`dashboard/src/hooks/useOverview.ts`** — Same pattern. Simple migration.
- **`dashboard/src/hooks/useAuth.ts`** — Uses raw fetch. Migrate to client but keep the auth context/provider structure.
- **`dashboard/src/components/`** — All UI components remain unchanged. Only hooks change.

### What NOT to Touch

- Do NOT modify `gateway/main.py` — static serving works
- Do NOT modify `dashboard/vite.config.ts` — proxy config works
- Do NOT modify any UI components in `dashboard/src/components/` — only hooks change
- Do NOT modify any backend routes, schemas, or services — this story is frontend + tooling only
- Do NOT add Recharts or any charting library — Story 5.2 owns that
- Do NOT add usage metering — Story 5.1 owns that
- Do NOT modify the sidebar, layout, or navigation — Story 4.1 owns that
- Do NOT add password reset flow — Story 4.5 owns that

### openapi-fetch Usage Pattern

```typescript
// dashboard/src/api/client.ts
import createClient from "openapi-fetch";
import type { paths } from "./schema"; // generated types

const client = createClient<paths>({
  credentials: "include", // cookie auth
});

export default client;
```

```typescript
// In a hook — example migration
import client from "@/api/client";

// Before (fetchJson):
const data = await fetchJson<OverviewData>("/dashboard/overview");

// After (openapi-fetch):
const { data, error } = await client.GET("/dashboard/overview");
```

**Key difference:** openapi-fetch returns `{ data, error, response }` — NOT a direct value. Hooks must destructure and handle errors from this shape.

### openapi-typescript Generation

```bash
# Generates schema.d.ts from running backend
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
```

The generated file exports `paths`, `components`, `operations` types. The `paths` type is what openapi-fetch uses for typed route matching.

### Error Handling with openapi-fetch

openapi-fetch does NOT throw on HTTP errors — it returns `{ data: undefined, error: ErrorBody }`. The hooks must check for errors explicitly:

```typescript
const { data, error } = await client.GET("/dashboard/overview");
if (error) {
  throw new Error(error.error?.message ?? "Request failed");
}
return data;
```

This replaces the `if (!res.ok) throw` pattern in `fetchJson`.

### Generated Types vs Manual Types

After migration, `dashboard/src/types/index.ts` should be reviewed:
- **Remove:** `ApiKey`, `OverviewData`, `SubnetOverview`, `SubnetRateLimits` — these come from generated types now
- **Keep:** Any UI-only types (e.g., form state, component props) that don't correspond to API schemas
- **Verify:** All component imports still resolve after type source changes

### Build Pipeline Flow

```
1. Start backend: `uv run uvicorn gateway.main:app`
2. Generate types: `cd dashboard && npm run generate-api`
   → openapi-typescript reads /openapi.json → writes src/api/schema.d.ts
3. Build dashboard: `npm run build`
   → tsc type-checks (including generated types) → vite bundles → dashboard/dist/
4. Backend serves dist/ automatically (main.py catch-all)
```

The `scripts/generate_api_client.sh` automates steps 1-2 (and stops the server after).

### Design System — Key Values (from Story 4.1/4.2/4.3)

No visual changes in this story. All design values remain unchanged.

### Project Structure Notes

New files:
```
scripts/
└── generate_api_client.sh          # OpenAPI → TypeScript generation script

dashboard/src/
└── api/
    ├── client.ts                   # openapi-fetch client instance
    └── schema.d.ts                 # Generated types (DO NOT EDIT manually)
```

Modified files:
- `dashboard/package.json` — add openapi-fetch, openapi-typescript, generate-api script
- `dashboard/src/hooks/useAuth.ts` — migrate from raw fetch to client
- `dashboard/src/hooks/useApiKeys.ts` — migrate from fetchJson to client
- `dashboard/src/hooks/useOverview.ts` — migrate from fetchJson to client
- `dashboard/src/types/index.ts` — remove API-derived types (now generated)

Potentially removed files:
- `dashboard/src/lib/api.ts` — `fetchJson` may no longer be needed

### Testing Standards

- **Backend:** Real Postgres and Redis required — use Docker test containers, never mock
- **Backend:** Mock only Bittensor SDK — everything else uses real infrastructure
- Run backend: `uv run pytest --tb=short -q`
- Lint backend: `uv run ruff check gateway/ tests/`
- Types backend: `uv run mypy gateway/`
- Types frontend: `cd dashboard && npx tsc --noEmit`
- Build frontend: `cd dashboard && npm run build`
- **510 backend tests currently pass** — this story must not break any existing tests

### Previous Story Intelligence (Story 4.3)

- **510 backend tests pass** — baseline for regression testing
- **Hand-crafted UI components** — shadcn-style, no Radix. This story doesn't add UI components, but don't modify existing ones.
- **f-string anti-pattern in structlog** — never use f-strings in structlog calls; use keyword args
- **Pattern: `credentials: "include"`** — all dashboard fetch calls must include this for cookie auth. The openapi-fetch client config handles this centrally.
- **Pattern: TanStack Query** — use `queryClient.invalidateQueries` after mutations for automatic list refresh. This pattern stays the same — only the fetch layer changes.
- **`fetchJson` was introduced in Story 4.3** — it's in `dashboard/src/lib/api.ts`. It was a step toward centralization; openapi-fetch completes the journey.
- **Code review patterns from 4.2/4.3:** Expect scrutiny on: credentials handling, error handling consistency, type safety, removal of dead code.

### Git Intelligence (Recent Commits)

- `992dee1` feat: add account overview dashboard (Story 4.3) (#33)
- `deaba2d` feat: add API key management dashboard (Story 4.2) (#32)
- `24cc47f` Merge PR #31: Story 4.1 dashboard shell and auth
- Pattern: feature branches merged via PR. Expected branch: `feat/story-4.4-api-client-generation-and-dashboard-build-pipeline`

### Security Considerations

- **No new sensitive data exposure** — this story changes the fetch layer, not what data is fetched
- **Cookie auth centralized** — `credentials: "include"` is configured once in the client, not per-hook. This is more secure than per-call configuration (can't forget it).
- **Generated `schema.d.ts` is NOT sensitive** — it's derived from the public OpenAPI spec (`/openapi.json` is public by default in FastAPI)
- **`generate_api_client.sh` starts a local server** — ensure it binds to localhost only and cleans up after itself

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 4, Story 4.4]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture — "API client: Generated via openapi-fetch from FastAPI's OpenAPI spec"]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — "dashboard/src/api/client.ts — openapi-fetch generated client"]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — "scripts/generate_api_client.sh — Regenerate TypeScript client from OpenAPI spec"]
- [Source: _bmad-output/implementation-artifacts/4-3-account-overview-and-quickstart.md — previous story dev notes]
- [Source: gateway/main.py:275-291 — static file serving and SPA catch-all]
- [Source: dashboard/vite.config.ts — dev proxy config for /openapi.json]
- [Source: dashboard/src/lib/api.ts — fetchJson utility to be replaced]
- [Source: dashboard/src/hooks/ — three hooks to migrate]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Installed `openapi-fetch` (^0.17.0) as runtime dep and `openapi-typescript` (^7.13.0) as dev dep. Added `generate-api` script to package.json.
- Task 2: Created `scripts/generate_api_client.sh` — tries running server first, falls back to Python spec extraction (no server needed). Generates `schema.d.ts` via openapi-typescript. Idempotent, executable.
- Task 3: Created `dashboard/src/api/client.ts` — openapi-fetch client with `credentials: "include"` and `paths` type from generated schema.
- Task 4: Migrated `useApiKeys.ts` — replaced `fetchJson` with typed `client.GET`, `client.POST`, `client.DELETE`. All 4 hooks (list, create, rotate, revoke) use generated types. TanStack Query wrapping preserved.
- Task 5: Migrated `useOverview.ts` — replaced `fetchJson` with `client.GET("/dashboard/overview")`. Generated `OverviewResponse` type used automatically.
- Task 6: Migrated `useAuth.ts` — replaced raw `fetch()` with `client.GET`/`client.POST` for all auth endpoints. Auth endpoints that return `JSONResponse` (me, login/dashboard, logout) have `unknown` response types in the schema — handled with type assertions. Auth flow (login, signup, logout, session check) preserved.
- Task 7: Cleaned up `types/index.ts` — API types now re-export from generated schema (`components["schemas"]`). Kept `User` and `AuthState` as frontend-only types. Removed `dashboard/src/lib/api.ts` (fetchJson no longer used). All component imports resolve correctly.
- Task 8: Verified end-to-end: `scripts/generate_api_client.sh` generates schema successfully, `npm run build` produces dist/ with no errors, `tsc --noEmit` passes clean.
- Task 9: Added `tests/api/test_openapi.py` — verifies `/openapi.json` returns valid OpenAPI 3.x spec with key endpoints. 511 total tests pass (510 existing + 1 new). Ruff clean, mypy clean, tsc clean, dashboard build clean.

### Change Log

- 2026-03-14: Story 4.4 implementation complete — API client generation pipeline with openapi-fetch, hook migrations, type cleanup
- 2026-03-14: Code review #1 — 8 issues fixed (1 HIGH, 4 MEDIUM, 3 LOW): extracted shared `extractErrorMessage` helper to `api/errors.ts`, standardized error handling on `if (error)` pattern across all hooks, removed dead `STARTED_SERVER` code and stderr suppression from `generate_api_client.sh`, eliminated duplicate `ApiKeyCreateRequest` type in `useApiKeys.ts`, removed unused type re-exports from `types/index.ts`

### File List

New files:
- scripts/generate_api_client.sh — OpenAPI spec → TypeScript types generation script
- dashboard/src/api/client.ts — openapi-fetch client instance with cookie auth
- dashboard/src/api/errors.ts — shared error message extraction helper
- dashboard/src/api/schema.d.ts — Generated TypeScript types from OpenAPI spec (DO NOT EDIT)
- tests/api/test_openapi.py — Backend test for /openapi.json endpoint

Modified files:
- dashboard/package.json — added openapi-fetch, openapi-typescript, generate-api script
- dashboard/package-lock.json — lockfile updated
- dashboard/src/hooks/useAuth.ts — migrated from raw fetch to openapi-fetch client
- dashboard/src/hooks/useApiKeys.ts — migrated from fetchJson to openapi-fetch client
- dashboard/src/hooks/useOverview.ts — migrated from fetchJson to openapi-fetch client
- dashboard/src/types/index.ts — API types re-exported from generated schema, unused exports removed

Removed files:
- dashboard/src/lib/api.ts — fetchJson utility no longer needed
