# Story 6.2: Operator Dashboard Views

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want a dedicated admin section in the dashboard,
so that I can visually monitor system health without querying API endpoints directly.

## Acceptance Criteria

1. **Given** I am logged in as an admin user
   **When** I navigate to the admin section
   **Then** I see a system health overview with per-subnet cards showing: request volume, error rate, p50/p95 latency, and miner availability
   **And** each card uses status indicators (green/amber/red with text labels — color never sole indicator)

2. **Given** the admin dashboard
   **When** I view metagraph status
   **Then** I see sync freshness per subnet with last sync timestamp and staleness duration
   **And** stale metagraphs (>5 minutes) are visually flagged with a warning indicator

3. **Given** the admin dashboard
   **When** I view developer activity
   **Then** I see a table of developers with: signup date, last active, total requests, per-subnet breakdown
   **And** summary metrics at the top: total developers, new signups this week, weekly active count

4. **Given** the admin dashboard
   **When** I view miner quality
   **Then** I see a per-subnet table of miners sorted by quality score
   **And** each row shows: miner UID, incentive score, gateway quality score, request count, average latency, error rate
   **And** miners with high error rates or zero recent requests are visually flagged

5. **Given** I am a regular developer (not admin)
   **When** I use the dashboard
   **Then** the admin section is not visible in the sidebar navigation
   **And** direct navigation to admin routes redirects to the overview page

## Tasks / Subtasks

- [x] Task 1: Expose `is_admin` in `/auth/me` response (AC: #5)
  - [x] 1.1 Modify `gateway/api/auth.py` → `me()` endpoint to include `is_admin` field in response: `{"id": str(org.id), "email": org.email, "is_admin": org.is_admin}`
  - [x] 1.2 Update `dashboard/src/types/index.ts` → add `is_admin: boolean` to `User` interface
  - [x] 1.3 Update `dashboard/src/hooks/useAuth.ts` → parse `is_admin` from `/auth/me` response and store in user state

- [x] Task 2: Add admin-aware routing and navigation (AC: #5)
  - [x] 2.1 Add admin routes in `dashboard/src/App.tsx` as nested children of `/dashboard`:
    - `/dashboard/admin` → `<Admin />` (overview/metrics page)
    - `/dashboard/admin/metagraph` → `<AdminMetagraph />`
    - `/dashboard/admin/developers` → `<AdminDevelopers />`
    - `/dashboard/admin/miners` → `<AdminMiners />`
  - [x] 2.2 Create `dashboard/src/components/auth/AdminRoute.tsx` — wraps children, checks `useAuth().user?.is_admin`, redirects to `/dashboard` if not admin
  - [x] 2.3 Update `dashboard/src/components/layout/Sidebar.tsx` — conditionally render admin nav section (with separator and "Admin" label) when `user.is_admin` is true. Add nav items: System Health, Metagraph, Developers, Miners. Use icons: `Shield`, `Network`, `Users`, `Cpu` from lucide-react.

- [x] Task 3: Create admin data hooks (AC: #1, #2, #3, #4)
  - [x] 3.1 Create `dashboard/src/hooks/useAdminMetrics.ts` — `useQuery` calling `GET /admin/metrics` with `time_range` param. Query key: `["admin-metrics", timeRange]`. `staleTime: 30_000`, `refetchInterval: 60_000`.
  - [x] 3.2 Create `dashboard/src/hooks/useAdminMetagraph.ts` — `useQuery` calling `GET /admin/metagraph`. Query key: `["admin-metagraph"]`. `staleTime: 10_000`, `refetchInterval: 30_000` (metagraph freshness matters).
  - [x] 3.3 Create `dashboard/src/hooks/useAdminDevelopers.ts` — `useQuery` calling `GET /admin/developers`. Query key: `["admin-developers"]`. `staleTime: 60_000`.
  - [x] 3.4 Create `dashboard/src/hooks/useAdminMiners.ts` — `useQuery` calling `GET /admin/miners`. Query key: `["admin-miners"]`. `staleTime: 30_000`, `refetchInterval: 60_000`.
  - [x] 3.5 NOTE: Admin endpoints are `include_in_schema=False`, so they won't be in the generated OpenAPI schema. Hooks must use `client.GET()` with manual path strings and define response types locally (not from `schema.d.ts`). Define admin response types in `dashboard/src/types/admin.ts`.

- [x] Task 4: Build System Health overview page (AC: #1)
  - [x] 4.1 Create `dashboard/src/pages/Admin.tsx` — main admin overview page
  - [x] 4.2 Create `dashboard/src/components/admin/SubnetHealthCard.tsx` — per-subnet card showing: request volume, error rate, p50/p95 latency, active miners. Status indicator: green (error rate <2%), amber (2-10%), red (>10%) with text labels ("Healthy", "Degraded", "Critical"). Use shadcn `Card`, `Badge`.
  - [x] 4.3 Add time range selector (reuse `DateRangeSelector` pattern from usage page) with options: 1h, 24h, 7d, 30d
  - [x] 4.4 Show summary row at top: total requests, overall error rate, total active miners across all subnets

- [x] Task 5: Build Metagraph Status page (AC: #2)
  - [x] 5.1 Create `dashboard/src/pages/AdminMetagraph.tsx`
  - [x] 5.2 Create `dashboard/src/components/admin/MetagraphStatusCard.tsx` — per-subnet card showing: last sync time (relative, e.g. "45s ago"), staleness duration, sync status badge (healthy/degraded/never_synced), consecutive failures count, active miners count
  - [x] 5.3 Stale metagraphs (staleness >300s) get amber/red warning with text: "Stale — last synced X minutes ago"
  - [x] 5.4 Show `last_sync_error` message if present

- [x] Task 6: Build Developer Activity page (AC: #3)
  - [x] 6.1 Create `dashboard/src/pages/AdminDevelopers.tsx`
  - [x] 6.2 Create `dashboard/src/components/admin/DeveloperSummaryCards.tsx` — top-level metric cards: total developers, new signups today, new this week, weekly active
  - [x] 6.3 Create `dashboard/src/components/admin/DeveloperTable.tsx` — sortable table using shadcn `Table` with columns: email, signup date, last active (relative time), total requests, per-subnet request counts. Default sort: last active (most recent first).
  - [x] 6.4 Handle empty state gracefully (no developers yet)

- [x] Task 7: Build Miner Quality page (AC: #4)
  - [x] 7.1 Create `dashboard/src/pages/AdminMiners.tsx`
  - [x] 7.2 Create `dashboard/src/components/admin/MinerTable.tsx` — per-subnet tables showing: miner UID, hotkey (truncated), incentive score, gateway quality score, request count, avg latency, error rate. Default sort: quality score (descending).
  - [x] 7.3 Visual flagging: miners with error rate >20% get red badge "High Errors". Miners with 0 recent requests get muted row with badge "Inactive".
  - [x] 7.4 Add subnet tabs/selector to switch between subnet miner tables

- [x] Task 8: Regenerate TypeScript API client (if needed) and test (AC: all)
  - [x] 8.1 Since admin endpoints are `include_in_schema=False`, the OpenAPI client does NOT need regeneration. Admin types are manually defined in `types/admin.ts`.
  - [x] 8.2 Build dashboard: `cd dashboard && npm run build` — verify no TypeScript errors
  - [x] 8.3 Verify all existing backend tests pass: `uv run pytest --tb=short -q`
  - [x] 8.4 Verify linter: `uv run ruff check gateway/ tests/`
  - [x] 8.5 Verify types: `uv run mypy gateway/`
  - [x] 8.6 Manual smoke test: log in as admin, verify admin nav appears; log in as regular user, verify admin nav is hidden

## Dev Notes

### Architecture Patterns and Constraints

- **Frontend-only story** — the admin API endpoints already exist from Story 6.1. This story adds React dashboard views that consume those endpoints.
- **One backend change required** — the `/auth/me` endpoint must return `is_admin` so the frontend knows whether to show admin navigation. This is a one-line change in `gateway/api/auth.py:191`.
- **Admin endpoints are NOT in OpenAPI schema** — Story 6.1 used `include_in_schema=False` on the admin router. The generated TypeScript client (`schema.d.ts`) does NOT have admin endpoint types. All admin data hooks must define response types manually in `dashboard/src/types/admin.ts` and use raw `client.GET()` calls with manual path strings and type assertions.
- **Cookie-based auth** — admin endpoints use the same JWT cookie auth as regular dashboard endpoints (`get_current_org_id()` → `require_admin`). The `client` already sends `credentials: "include"`, so admin requests work automatically — no extra auth headers needed.
- **No new backend tests** — Story 6.1 covers all admin endpoint testing. This story only adds frontend views.
- **React Router v6** — nested routes under `/dashboard`. Admin routes nest as `/dashboard/admin/*`.
- **TanStack Query** — all data fetching uses `useQuery` hooks. Follow the exact patterns in `useUsage.ts`, `useApiKeys.ts`.
- **shadcn/ui + Tailwind** — use existing shadcn components (`Card`, `Table`, `Badge`, `Button`, `Tabs`). Run `npx shadcn@latest add <component>` from `dashboard/` directory if a new component is needed.
- **Semantic color tokens** — use `text-foreground`, `text-muted-foreground`, `bg-background`, `bg-surface`, `bg-elevated`, `border-border`. Never hardcode colors.
- **lucide-react** for icons — already installed, used throughout sidebar and pages.
- **Status indicators must include text labels** — per AC #1, color is never the sole indicator. Always pair green/amber/red with text like "Healthy", "Degraded", "Critical".

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| Admin API endpoints (metrics, metagraph, developers, miners) | EXISTS (Story 6.1) | `gateway/api/admin.py` |
| `require_admin` dependency | EXISTS (Story 6.1) | `gateway/middleware/auth.py` |
| `is_admin` on Organization model | EXISTS (Story 6.1) | `gateway/models/organization.py` |
| Admin Pydantic schemas | EXISTS (Story 6.1) | `gateway/schemas/admin.py` |
| `/auth/me` endpoint | EXISTS, needs `is_admin` added | `gateway/api/auth.py:169-191` |
| Dashboard routing | EXISTS | `dashboard/src/App.tsx` |
| Sidebar navigation | EXISTS, needs admin section | `dashboard/src/components/layout/Sidebar.tsx` |
| `useAuth` hook | EXISTS, needs `is_admin` in User type | `dashboard/src/hooks/useAuth.ts` |
| `User` type | EXISTS, needs `is_admin` field | `dashboard/src/types/index.ts` |
| `DateRangeSelector` component | EXISTS (reusable) | `dashboard/src/components/usage/DateRangeSelector.tsx` |
| shadcn `Card`, `Table`, `Badge`, `Button`, `Tabs` | EXISTS | `dashboard/src/components/ui/` |
| Admin pages (Admin, AdminMetagraph, AdminDevelopers, AdminMiners) | DOES NOT EXIST | — |
| Admin components | DOES NOT EXIST | — |
| Admin hooks | DOES NOT EXIST | — |
| Admin types | DOES NOT EXIST | — |
| `AdminRoute` guard component | DOES NOT EXIST | — |

### Existing Code to Leverage — DO NOT REINVENT

- **`dashboard/src/hooks/useUsage.ts`** — REFERENCE for hook pattern: `useQuery` with `client.GET()`, error extraction, query key naming, staleTime/refetchInterval config.
- **`dashboard/src/pages/Usage.tsx`** — REFERENCE for page structure: header, loading skeleton, error alert, data display with Cards.
- **`dashboard/src/components/usage/DateRangeSelector.tsx`** — REUSE for time range selection on the System Health page. It already supports selectable ranges.
- **`dashboard/src/components/usage/subnet-constants.ts`** — REUSE `SUBNET_DISPLAY_NAMES` for human-readable subnet names in admin views.
- **`dashboard/src/components/layout/Sidebar.tsx`** — EXTEND with admin nav items. Follow the existing `navItems` array pattern.
- **`dashboard/src/components/auth/ProtectedRoute.tsx`** — REFERENCE for `AdminRoute` pattern. Same concept: check auth state, redirect if unauthorized.
- **`dashboard/src/api/client.ts`** — USE for all API calls. `client.GET()` with `credentials: "include"` handles auth automatically.
- **`dashboard/src/api/errors.ts`** — USE `extractErrorMessage()` for error handling in hooks.
- **`dashboard/src/lib/utils.ts`** — USE `cn()` for conditional Tailwind classes.

### What NOT to Touch

- Do NOT modify any admin API endpoints — they're complete from Story 6.1
- Do NOT regenerate the OpenAPI TypeScript client — admin endpoints are intentionally excluded from the schema
- Do NOT modify rate limiting, auth middleware, or any backend logic
- Do NOT add backend tests — admin endpoint tests exist from Story 6.1
- Do NOT modify existing developer-facing dashboard pages (Dashboard, ApiKeys, Usage, Settings)
- Do NOT add email sending, alerting, or notification features — Phase 2
- Do NOT hardcode color values — use semantic tokens from the Tailwind theme

### Admin Type Definitions

Since admin endpoints are excluded from the OpenAPI schema, define types manually in `dashboard/src/types/admin.ts`. Match the Pydantic schemas from `gateway/schemas/admin.py` exactly:

```typescript
// dashboard/src/types/admin.ts

export interface SubnetMetrics {
  subnet_name: string;
  netuid: number;
  request_count: number;
  success_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
}

export interface MetricsResponse {
  time_range: string;
  subnets: SubnetMetrics[];
  total_requests: number;
  total_errors: number;
  overall_error_rate: number;
}

export interface SubnetMetagraphStatus {
  netuid: number;
  subnet_name: string;
  last_sync_time: string | null;
  staleness_seconds: number;
  is_stale: boolean;
  sync_status: "healthy" | "degraded" | "never_synced";
  last_sync_error: string | null;
  consecutive_failures: number;
  active_miners: number;
}

export interface MetagraphResponse {
  subnets: SubnetMetagraphStatus[];
}

export interface DeveloperSummary {
  org_id: string;
  email: string;
  signup_date: string;
  last_active: string | null;
  total_requests: number;
  requests_by_subnet: Record<string, number>;
}

export interface DeveloperMetrics {
  total_developers: number;
  new_signups_today: number;
  new_signups_this_week: number;
  weekly_active_developers: number;
  developers: DeveloperSummary[];
}

export interface MinerInfo {
  miner_uid: number;
  hotkey: string;
  netuid: number;
  subnet_name: string;
  incentive_score: number;
  gateway_quality_score: number;
  total_requests: number;
  successful_requests: number;
  avg_latency_ms: number;
  error_rate: number;
}

export interface MinerResponse {
  subnets: Record<string, MinerInfo[]>;
}
```

### API Call Pattern for Admin Hooks

Because admin paths aren't in the generated schema, use this pattern:

```typescript
// In useAdminMetrics.ts
import client from "@/api/client";
import type { MetricsResponse } from "@/types/admin";

export function useAdminMetrics(timeRange: string = "24h") {
  return useQuery({
    queryKey: ["admin-metrics", timeRange],
    queryFn: async () => {
      const response = await fetch(`/admin/metrics?time_range=${timeRange}`, {
        credentials: "include",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? `Request failed: ${response.status}`);
      }
      return response.json() as Promise<MetricsResponse>;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
```

Note: Since `client.GET()` from openapi-fetch requires typed paths from the schema, and admin paths aren't in the schema, use native `fetch()` with `credentials: "include"` instead. This avoids TypeScript errors from unrecognized paths.

### Status Indicator Design

For subnet health cards (AC #1):

| Error Rate | Color | Text Label | Badge Variant |
|---|---|---|---|
| < 2% | Green | Healthy | `default` with green bg |
| 2% – 10% | Amber | Degraded | `secondary` with amber bg |
| > 10% | Red | Critical | `destructive` |

Always render the text label alongside the color. Example:
```tsx
<Badge className={cn(
  errorRate < 0.02 ? "bg-green-100 text-green-800" :
  errorRate < 0.10 ? "bg-amber-100 text-amber-800" :
  "bg-red-100 text-red-800"
)}>
  {errorRate < 0.02 ? "Healthy" : errorRate < 0.10 ? "Degraded" : "Critical"}
</Badge>
```

### Sidebar Admin Section Design

Add admin nav items after the Settings separator, before Docs. Only render when `user.is_admin` is true:

```
Overview        ← existing
API Keys        ← existing
Usage           ← existing
─────────────
Settings        ← existing
─────────────
Admin           ← NEW section label (text-xs, text-muted-foreground, uppercase)
  System Health ← NEW (Shield icon)
  Metagraph     ← NEW (Network icon)
  Developers    ← NEW (Users icon)
  Miners        ← NEW (Cpu icon)
─────────────
Docs            ← existing
```

### Project Structure Notes

New files:
```
dashboard/src/
├── types/
│   └── admin.ts                           # Admin response types (manual, not generated)
├── hooks/
│   ├── useAdminMetrics.ts                 # System metrics hook
│   ├── useAdminMetagraph.ts               # Metagraph status hook
│   ├── useAdminDevelopers.ts              # Developer activity hook
│   └── useAdminMiners.ts                  # Miner quality hook
├── pages/
│   ├── Admin.tsx                          # System Health overview page
│   ├── AdminMetagraph.tsx                 # Metagraph status page
│   ├── AdminDevelopers.tsx                # Developer activity page
│   └── AdminMiners.tsx                    # Miner quality page
├── components/
│   ├── auth/
│   │   └── AdminRoute.tsx                 # Admin route guard
│   └── admin/
│       ├── SubnetHealthCard.tsx            # Per-subnet health card
│       ├── MetagraphStatusCard.tsx         # Per-subnet metagraph card
│       ├── DeveloperSummaryCards.tsx       # Top-level developer metrics
│       ├── DeveloperTable.tsx             # Sortable developer table
│       └── MinerTable.tsx                 # Per-subnet miner table
```

Modified files:
```
gateway/api/auth.py                        # Add is_admin to /auth/me response
dashboard/src/types/index.ts               # Add is_admin to User interface
dashboard/src/hooks/useAuth.ts             # Parse is_admin from /auth/me
dashboard/src/App.tsx                      # Add admin routes
dashboard/src/components/layout/Sidebar.tsx # Add admin nav section
```

### Testing Standards

- **No new backend tests** — admin endpoints are fully tested in Story 6.1
- **One backend change needs verification** — the `is_admin` field in `/auth/me`. Extend existing `/auth/me` tests in `tests/api/test_auth.py` to verify `is_admin` is returned (test both admin=True and admin=False orgs)
- **Dashboard build** — `cd dashboard && npm run build` must succeed with zero TypeScript errors
- **After completion**: Run `uv run pytest --tb=short -q`, `uv run ruff check gateway/ tests/`, `uv run mypy gateway/`
- **Manual smoke test checklist**:
  - Log in as admin → admin nav items visible
  - Log in as regular user → admin nav hidden
  - Direct navigate to `/dashboard/admin` as regular user → redirected to `/dashboard`
  - System Health page loads with subnet cards
  - Metagraph page shows sync status
  - Developers page shows table with summary cards
  - Miners page shows per-subnet miner tables

### Previous Story Intelligence (Story 6.1)

- **Story 6.1 creates the admin API endpoints** — this story MUST be implemented after 6.1 is complete
- **Admin auth uses `require_admin` dependency** — wraps `get_current_org_id()` + checks `is_admin` on Organization. Returns 403 for non-admin, 401 for unauthenticated.
- **Admin endpoints are hidden from OpenAPI** — `include_in_schema=False` on the admin router mount. This means the TypeScript client can't type-check admin API calls. Manual types required.
- **Admin response schemas** are in `gateway/schemas/admin.py` — mirror these exactly in `dashboard/src/types/admin.ts`
- **`is_admin` column** on Organization defaults to `False`. Set in DB directly (no self-service promotion).
- **Branch naming**: `feat/story-6.2-operator-dashboard-views`
- **Commit messages**: `feat: add <description> (Story 6.2)`

### Git Intelligence (Recent Commits)

- `2a746fa` chore: add Story 6.1 spec, code scan plan, and uncommitted dashboard assets (#38)
- `faab268` feat: add per-key debug mode with content logging and 48h cleanup (Story 5.3) (#37)
- `f60454c` feat: add usage dashboard with Recharts charts, quota display, and code quality fixes (Story 5.2) (#36)
- Pattern: feature branches merged via PR with squash
- Expected branch: `feat/story-6.2-operator-dashboard-views`
- Dashboard patterns established in Stories 4.1-5.2: shadcn components, TanStack Query hooks, semantic color tokens

### Security Considerations

- **Admin route guard is client-side only** — `AdminRoute` hides UI but the real security is server-side (`require_admin` dependency on all `/admin/*` endpoints). Even if a non-admin navigates to admin routes, the API calls will return 403.
- **Developer emails are visible in admin developer table** — acceptable for sole operator (Cevin). If multiple admins are added later, consider email masking.
- **No sensitive data in admin response types** — API keys, passwords, and wallet keys are never included in admin endpoint responses.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6, Story 6.2]
- [Source: _bmad-output/planning-artifacts/prd.md#FR37 — Operator: request volume, error rates, latency]
- [Source: _bmad-output/planning-artifacts/prd.md#FR38 — Operator: metagraph sync status]
- [Source: _bmad-output/planning-artifacts/prd.md#FR39 — Operator: signup and activity metrics]
- [Source: _bmad-output/planning-artifacts/prd.md#FR40 — Operator: miner quality scores]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture — React SPA, TanStack Query, Recharts]
- [Source: _bmad-output/planning-artifacts/architecture.md#API Boundaries — /admin/* require admin-level auth]
- [Source: _bmad-output/planning-artifacts/architecture.md#TypeScript/React Naming — PascalCase components, camelCase hooks]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Operator dashboard separation]
- [Source: _bmad-output/implementation-artifacts/6-1-admin-api-endpoints.md — Admin API endpoint design and schemas]
- [Source: gateway/api/auth.py:169-191 — /auth/me endpoint, needs is_admin field]
- [Source: gateway/schemas/admin.py — Admin Pydantic schemas to mirror in TypeScript]
- [Source: dashboard/src/hooks/useUsage.ts — Reference hook pattern]
- [Source: dashboard/src/pages/Usage.tsx — Reference page pattern]
- [Source: dashboard/src/components/layout/Sidebar.tsx — Sidebar nav structure]
- [Source: dashboard/src/components/usage/DateRangeSelector.tsx — Reusable time range selector]
- [Source: dashboard/src/components/usage/subnet-constants.ts — SUBNET_DISPLAY_NAMES for human-readable names]
- [Source: dashboard/src/App.tsx — Router structure, nested routes]
- [Source: dashboard/src/hooks/useAuth.ts — Auth context, User state]
- [Source: dashboard/src/types/index.ts — User interface, API type re-exports]
- [Source: dashboard/src/components/auth/ProtectedRoute.tsx — Auth guard pattern]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- All 8 tasks completed: is_admin in /auth/me, admin routing, admin hooks, system health page, metagraph page, developer activity page, miner quality page, verification
- 578 total tests passing (7 new: is_admin=false in /auth/me, is_admin=true for admin user)
- Dashboard builds with zero TypeScript errors
- Linter (ruff) and type checker (mypy) pass clean
- Admin types manually defined in types/admin.ts (admin endpoints excluded from OpenAPI schema)
- Admin hooks use native fetch() with credentials: "include" (not openapi-fetch client)
- Status indicators include text labels alongside color (accessibility per AC #1)
- AdminRoute guard redirects non-admin users to /dashboard
- Sidebar conditionally renders admin section when user.is_admin is true

### Change Log

- 2026-03-14: Story 6.2 implemented — operator dashboard views with admin routing, system health, metagraph status, developer activity, and miner quality pages
- 2026-03-14: Code review fixes — Added /admin Vite proxy (H1), re-fetch /auth/me after login for is_admin (H2), passed isAdmin to mobile sidebar (H3), fixed dark-mode error colors (H4), extracted shared formatRelativeTime and adminFetch utilities (M1/M5), added accessible sortable headers with useMemo (M2/M3), fixed stale warning color consistency (M4), added refetchInterval to useAdminDevelopers (M6), added hotkey tooltip (L1), added admin nav aria-label (L2), named magic number constant (L5)

### File List

New files:
- dashboard/src/types/admin.ts
- dashboard/src/hooks/useAdminMetrics.ts
- dashboard/src/hooks/useAdminMetagraph.ts
- dashboard/src/hooks/useAdminDevelopers.ts
- dashboard/src/hooks/useAdminMiners.ts
- dashboard/src/components/auth/AdminRoute.tsx
- dashboard/src/components/admin/SubnetHealthCard.tsx
- dashboard/src/components/admin/MetagraphStatusCard.tsx
- dashboard/src/components/admin/DeveloperSummaryCards.tsx
- dashboard/src/components/admin/DeveloperTable.tsx
- dashboard/src/components/admin/MinerTable.tsx
- dashboard/src/pages/Admin.tsx
- dashboard/src/pages/AdminMetagraph.tsx
- dashboard/src/pages/AdminDevelopers.tsx
- dashboard/src/pages/AdminMiners.tsx
- dashboard/src/lib/format.ts
- dashboard/src/api/adminFetch.ts

Modified files:
- gateway/api/auth.py (added is_admin to /auth/me response)
- dashboard/src/types/index.ts (added is_admin to User interface)
- dashboard/src/hooks/useAuth.ts (re-fetch /auth/me after login for is_admin)
- dashboard/src/App.tsx (added admin routes with AdminRoute guard)
- dashboard/src/components/layout/Sidebar.tsx (added admin nav section with aria-label)
- dashboard/src/components/layout/DashboardLayout.tsx (pass isAdmin prop to all Sidebar instances)
- dashboard/vite.config.ts (added /admin proxy)
- tests/api/test_auth_cookies.py (added is_admin tests for /auth/me)
