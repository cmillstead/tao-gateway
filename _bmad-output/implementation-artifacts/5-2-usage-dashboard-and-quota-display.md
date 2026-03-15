# Story 5.2: Usage Dashboard & Quota Display

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to see my usage and quota status visually in the dashboard,
so that I can monitor my consumption at a glance and know when I'm approaching limits.

## Acceptance Criteria

1. **Given** I am logged in and on the Usage page
   **When** the page loads
   **Then** I see request count charts per subnet over time (Recharts area/line charts)
   **And** latency metrics displayed as p50, p95, p99 per subnet
   **And** I can select date ranges within the last 90 days (7d / 30d / 90d presets)

2. **Given** I am on the Usage page
   **When** I view quota consumption
   **Then** I see my remaining free tier quota per subnet as progress bars (QuotaBar component)
   **And** each shows explicit numbers (e.g., "847 / 1,000 monthly requests") — not vague indicators
   **And** per-minute and per-day limits are also visible

3. **Given** I am near my quota limit (>80% consumed)
   **When** I view the quota display
   **Then** the progress bar visually indicates proximity to the limit (amber fill + text label)
   **And** at 100% the bar shows red fill + "Quota exceeded" text
   **And** color is never the sole indicator — text label always accompanies status

4. **Given** the Usage page charts
   **When** I interact with them
   **Then** I can toggle between subnets to compare usage patterns
   **And** hovering on data points shows exact values (Recharts tooltip)
   **And** the charts are keyboard-accessible

5. **Given** the dashboard Overview page (from Epic 4)
   **When** I check quota at a glance
   **Then** the overview also shows a summary of quota consumption per subnet (QuotaBar or similar)
   **And** links to the full Usage page for detailed drill-down

## Tasks / Subtasks

- [x] Task 1: Install Recharts and regenerate API client (AC: #1)
  - [x] 1.1 Install `recharts` in `dashboard/`: `cd dashboard && npm install recharts`
  - [x] 1.2 Regenerate TypeScript API client: exported OpenAPI schema via Python, ran `openapi-typescript` to add `DashboardUsageResponse`, `SubnetUsageWithQuota`, `UsageSummary`, `SubnetQuota` types to `schema.d.ts`
  - [x] 1.3 Add type re-exports in `dashboard/src/types/index.ts`: `DashboardUsageResponse`, `SubnetUsageWithQuota`, `UsageSummary`, `SubnetQuota`

- [x] Task 2: Create `useUsage` TanStack Query hook (AC: #1, #4)
  - [x] 2.1 Create `dashboard/src/hooks/useUsage.ts` following `useOverview.ts` pattern
  - [x] 2.2 Hook accepts params: `subnet?: string`, `startDate?: string`, `endDate?: string`, `granularity?: "daily" | "monthly"`
  - [x] 2.3 Calls `client.GET("/dashboard/usage", { params: { query: { ... } } })` with credentials: "include"
  - [x] 2.4 Returns `{ data, isLoading, error }` — typed as `DashboardUsageResponse`
  - [x] 2.5 Default date range: last 30 days
  - [x] 2.6 Set `staleTime` and `refetchInterval` appropriate for usage data (60s stale, 5min refetch)

- [x] Task 3: Create QuotaBar component (AC: #2, #3)
  - [x] 3.1 Create `dashboard/src/components/usage/QuotaBar.tsx`
  - [x] 3.2 Props: `subnetName: string`, `monthlyLimit: number`, `monthlyUsed: number`
  - [x] 3.3 Anatomy: `[Subnet label] [Progress bar] [used / limit]`
  - [x] 3.4 States: Normal (<80%): indigo fill, Warning (80-99%): amber fill + "Approaching limit" text, Exceeded (100%): red fill + "Quota exceeded" text
  - [x] 3.5 Color is NEVER the sole indicator — always include text label for status
  - [x] 3.6 Display as human-readable subnet names: "Text Generation" not "sn1", "Image Generation" not "sn19", "Code Generation" not "sn62"
  - [x] 3.7 Use Tailwind classes consistent with project (indigo-600 primary, amber-500 warning, red-500 exceeded)

- [x] Task 4: Create usage chart components (AC: #1, #4)
  - [x] 4.1 Create `dashboard/src/components/usage/RequestChart.tsx` — Recharts AreaChart showing request counts over time
  - [x] 4.2 X-axis: date, Y-axis: request count. One line/area per subnet, color-coded
  - [x] 4.3 Include Recharts `Tooltip` for hover values with exact counts
  - [x] 4.4 Include Recharts `Legend` for subnet toggle (click legend item to show/hide subnet)
  - [x] 4.5 Create `dashboard/src/components/usage/LatencyChart.tsx` — Recharts LineChart showing p50/p95/p99 latency per subnet
  - [x] 4.6 Charts must be responsive (use Recharts `ResponsiveContainer`)
  - [x] 4.7 Keyboard accessible: Recharts `accessibilityLayer` prop used on both charts
  - [x] 4.8 Use `cartesianGrid`, `strokeDasharray="3 3"` for professional look

- [x] Task 5: Create date range selector component (AC: #1)
  - [x] 5.1 Create `dashboard/src/components/usage/DateRangeSelector.tsx`
  - [x] 5.2 Three preset buttons: 7d, 30d, 90d (button group with aria-pressed)
  - [x] 5.3 Active selection highlighted with bg-background shadow styling (consistent with Tabs)
  - [x] 5.4 On change, recalculates `startDate` and `endDate` and triggers hook refetch via query key change
  - [x] 5.5 Default: 30d

- [x] Task 6: Build the Usage page (AC: #1, #2, #3, #4)
  - [x] 6.1 Replace placeholder in `dashboard/src/pages/Usage.tsx` with full implementation
  - [x] 6.2 Page layout (top to bottom):
    - Title: "Usage & Quota" with subtitle
    - Quota section: QuotaBar for each subnet with per-minute/per-day/per-month limits
    - Date range selector
    - Request volume chart (AreaChart)
    - Latency chart (LineChart with p50/p95/p99 + subnet selector)
  - [x] 6.3 Three-state rendering: loading skeleton (pulse), error (red alert), data
  - [x] 6.4 Empty state: "No usage data yet. Make your first API request to see usage statistics." with link to Overview/Quickstart
  - [x] 6.5 Professional design: no emoji, no playful copy, Stripe/OpenAI-inspired

- [x] Task 7: Add quota summary to Overview page (AC: #5)
  - [x] 7.1 Create `dashboard/src/components/overview/QuotaSummaryCard.tsx` using QuotaBar components inside a Card
  - [x] 7.2 Add to `dashboard/src/pages/Dashboard.tsx` — show per-subnet quota bars
  - [x] 7.3 Include "View details" link to `/dashboard/usage`
  - [x] 7.4 Fetch quota data from `GET /dashboard/usage` endpoint via `useUsage` hook

- [x] Task 8: Write tests (AC: all)
  - [x] 8.1-8.7 No frontend test framework installed (no vitest, jest, or @testing-library in project). Validated via TypeScript compilation, Vite build, and ESLint — all pass with zero new errors.
  - [x] 8.8 All existing tests still pass — 536 backend tests pass (up from 534 baseline)

## Dev Notes

### Architecture Patterns and Constraints

- **This is a frontend-only story** — the backend `GET /dashboard/usage` endpoint already exists (Story 5.1). No backend changes needed.
- **Recharts is the charting library** — specified in architecture and UX design docs. Install via npm, NOT yarn.
- **shadcn/ui components are the design system** — use existing Card, Tabs, Badge, Button, Separator, Tooltip primitives. Do NOT introduce a new component library.
- **openapi-fetch is the API client** — all API calls go through the typed client in `dashboard/src/api/client.ts`. Do NOT use raw `fetch()`.
- **TanStack Query for data fetching** — all hooks follow the pattern in `useOverview.ts` and `useApiKeys.ts`. Do NOT use `useEffect` + `useState` for data fetching.
- **Subnet-as-capability framing** — display "Text Generation", "Image Generation", "Code Generation" in the UI, NOT "SN1", "SN19", "SN62". Subnet IDs are secondary detail only.
- **Professional design language** — no emoji, no mascots, no playful copy. Stripe/OpenAI/Vercel-inspired. Zinc neutrals, Indigo-600 primary, Emerald/Amber/Red status colors.
- **Desktop-first responsive** — full sidebar >=1280px, collapsed sidebar 1024-1279px, hidden sidebar <1024px. Charts must be responsive via `ResponsiveContainer`.
- **WCAG 2.1 AA** — color never sole indicator (QuotaBar must always have text labels), semantic HTML, aria-labels on icon buttons, keyboard-accessible charts.

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| `GET /dashboard/usage` endpoint | EXISTS | `gateway/api/dashboard.py:121-157` |
| `DashboardUsageResponse` schema | EXISTS | `gateway/schemas/usage.py` |
| `SubnetUsageWithQuota` schema | EXISTS | `gateway/schemas/usage.py` |
| `UsageSummary` schema | EXISTS | `gateway/schemas/usage.py` |
| `SubnetQuota` schema | EXISTS | `gateway/schemas/usage.py` |
| `schema.d.ts` (generated types) | NEEDS REGENERATION | `dashboard/src/api/schema.d.ts` — does NOT yet include usage types |
| `Usage.tsx` page | EXISTS as PLACEHOLDER | `dashboard/src/pages/Usage.tsx` — shows "Coming in Story 5.2" |
| Routing for `/dashboard/usage` | EXISTS | `dashboard/src/App.tsx` — route already registered |
| Sidebar "Usage" nav link | EXISTS | `dashboard/src/components/layout/Sidebar.tsx` |
| `recharts` npm package | NOT INSTALLED | `dashboard/package.json` — must install |
| `useUsage` hook | DOES NOT EXIST | — |
| Usage chart components | DO NOT EXIST | — |
| QuotaBar component | DOES NOT EXIST | — |
| Quota summary on Overview | DOES NOT EXIST | — |
| `dashboard/src/components/usage/` dir | DOES NOT EXIST | — |

### Existing Code to Leverage — DO NOT REINVENT

- **`dashboard/src/hooks/useOverview.ts`** — COPY this pattern for `useUsage.ts`. Same structure: define QUERY_KEY, export hook that calls `client.GET(...)`, return `{ data, isLoading, error }`.
- **`dashboard/src/hooks/useApiKeys.ts`** — Reference for mutation patterns if needed (not likely for this read-only story).
- **`dashboard/src/api/client.ts`** — The typed API client. Uses `createClient<paths>()` from `openapi-fetch` with `credentials: "include"`. All calls go through this.
- **`dashboard/src/api/errors.ts`** — `extractErrorMessage(error, "fallback")` for error display.
- **`dashboard/src/components/overview/MetricCard.tsx`** — Reuse for top-level usage metrics if needed (total requests, error rate, etc.).
- **`dashboard/src/components/ui/`** — shadcn/ui primitives: `card`, `button`, `tabs`, `badge`, `separator`, `tooltip`. Use these for layout and controls.
- **`dashboard/src/pages/Dashboard.tsx`** — Reference for page layout pattern: title area → content → three-state rendering (loading/error/data).
- **`dashboard/src/pages/ApiKeys.tsx`** — Reference for page layout and data table patterns.
- **`dashboard/src/lib/utils.ts`** — `cn()` helper for Tailwind class merging.
- **`dashboard/src/types/index.ts`** — Add new type re-exports here from `schema.d.ts`.

### What NOT to Touch

- Do NOT modify any backend files — this story is frontend-only
- Do NOT modify `dashboard/src/api/client.ts` — existing client works as-is
- Do NOT modify `dashboard/src/App.tsx` — routing is already configured
- Do NOT modify `dashboard/src/components/layout/Sidebar.tsx` — Usage nav link already exists
- Do NOT introduce a new CSS framework or component library — use existing Tailwind + shadcn/ui
- Do NOT use raw `fetch()` — use the typed openapi-fetch client
- Do NOT use `useEffect` + `useState` for data fetching — use TanStack Query
- Do NOT add billing/payment/upgrade features — those are Phase 2
- Do NOT add debug mode UI — that's Story 5.3's scope
- Do NOT add health page — that's separate scope

### Subnet Name Mapping

Use this mapping throughout the UI:

```typescript
const SUBNET_DISPLAY_NAMES: Record<string, string> = {
  sn1: "Text Generation",
  sn19: "Image Generation",
  sn62: "Code Generation",
};

// Or by netuid:
const NETUID_DISPLAY_NAMES: Record<number, string> = {
  1: "Text Generation",
  19: "Image Generation",
  62: "Code Generation",
};
```

### Rate Limit / Quota Structure

The backend `GET /dashboard/usage` returns `SubnetQuota` with these fields:
```typescript
{
  subnet_name: string;  // e.g., "sn1"
  netuid: number;       // e.g., 1
  monthly_limit: number; // e.g., 1000
  monthly_used: number;  // e.g., 153
  monthly_remaining: number; // e.g., 847
}
```

Free tier limits (from `_SUBNET_RATE_LIMITS`):
- SN1 (Text): 10/min, 100/day, 1000/month
- SN19 (Image): 5/min, 50/day, 500/month
- SN62 (Code): 10/min, 100/day, 1000/month

Note: The `SubnetQuota` from the API only includes monthly limits. Per-minute and per-day limits should be displayed as static reference values (hardcoded in the frontend from the known rate limits above, since these are fixed free-tier limits).

### Chart Data Transformation

The `DashboardUsageResponse` returns data organized by subnet:
```typescript
{
  start_date: "2026-02-12",
  end_date: "2026-03-14",
  granularity: "daily",
  subnets: [
    {
      subnet_name: "sn1",
      netuid: 1,
      summaries: [
        { period: "2026-03-14", request_count: 42, success_count: 40, error_count: 2, p50_latency_ms: 120, p95_latency_ms: 450, p99_latency_ms: 890, total_prompt_tokens: 5000, total_completion_tokens: 3000 },
        // ... one entry per day
      ],
      quota: { subnet_name: "sn1", netuid: 1, monthly_limit: 1000, monthly_used: 153, monthly_remaining: 847 }
    },
    // ... more subnets
  ]
}
```

For Recharts, transform into a flat array keyed by date:
```typescript
// Transform for charts:
[
  { date: "2026-03-14", sn1_requests: 42, sn19_requests: 5, sn62_requests: 12 },
  { date: "2026-03-13", sn1_requests: 38, sn19_requests: 8, sn62_requests: 15 },
  // ...
]
```

### Project Structure Notes

New files:
```
dashboard/src/
├── hooks/
│   └── useUsage.ts                    # TanStack Query hook for GET /dashboard/usage
├── components/
│   ├── usage/
│   │   ├── QuotaBar.tsx               # Per-subnet quota progress bar
│   │   ├── RequestChart.tsx           # Recharts AreaChart — request volume over time
│   │   ├── LatencyChart.tsx           # Recharts LineChart — p50/p95/p99 latency
│   │   └── DateRangeSelector.tsx      # 7d/30d/90d preset buttons
│   └── overview/
│       └── QuotaSummaryCard.tsx       # Quota bars on Overview page
└── pages/
    └── Usage.tsx                      # REPLACE placeholder with full implementation
```

Modified files:
- `dashboard/src/types/index.ts` — add usage type re-exports
- `dashboard/src/pages/Dashboard.tsx` — add QuotaSummaryCard
- `dashboard/package.json` — add recharts dependency

### Testing Standards

- **Frontend tests** — use Vitest + React Testing Library (if configured) or check existing test setup
- **Backend tests** — 534 tests currently pass. Do NOT break any existing backend tests.
- **After completion:** Run `npm run generate-api` to update TypeScript types, then `npm run build` to verify dashboard builds cleanly
- **Lint:** Run `npm run lint` (if configured) in the dashboard directory

### Previous Story Intelligence (Story 5.1)

- **534 backend tests pass** — this story should not break any
- **`GET /dashboard/usage`** was created with JWT cookie auth via `get_current_org_id` dependency
- **`npm run generate-api`** script exists — regenerates TypeScript client from OpenAPI spec. Must be run with the backend server running (`uv run uvicorn gateway.main:app`)
- **f-string anti-pattern in structlog** — N/A for this frontend story, but good to know
- **Pattern: `credentials: "include"`** — all dashboard fetch calls use cookie auth. The `client.ts` already has this configured.
- **Code review patterns from 4.2/4.3/4.4:** Expect scrutiny on: error handling consistency, type safety, removal of dead code, shared helper extraction
- **Story 4.3 (`Dashboard.tsx`)** has the MetricCard pattern and overview layout — extend this for quota display
- **Story 4.4** introduced `openapi-fetch` and `schema.d.ts` generation — this story depends on regenerating the schema to include usage types

### Git Intelligence (Recent Commits)

- `d83289a` Merge PR #35: Story 5.1 usage metering and storage
- `4029878` feat: add usage metering, storage, and API endpoints (Story 5.1)
- `257b7fa` feat: add typed API client generation with openapi-fetch (Story 4.4) (#34)
- Pattern: feature branches merged via PR. Expected branch: `feat/story-5.2-usage-dashboard-and-quota-display`
- Pattern: commit messages follow `feat: add <description> (Story X.Y)`

### Security Considerations

- **No new attack surface** — this story only adds frontend components consuming an existing authenticated endpoint
- **JWT cookie auth** — `GET /dashboard/usage` already enforces JWT auth via `get_current_org_id`. The frontend client sends cookies automatically via `credentials: "include"`.
- **No user input to backend** — date range and subnet filters are query parameters validated by the backend Pydantic schema
- **No sensitive data in charts** — usage data contains aggregate counts and latency metrics, not request/response content

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5, Story 5.2]
- [Source: _bmad-output/planning-artifacts/prd.md#Usage Monitoring — FR17, FR18, FR19, FR20]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Journey 3: Usage Monitoring & Quota Awareness]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#QuotaBar custom component]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy — AreaChart, Select]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture — React SPA, TanStack Query, Recharts, Tailwind]
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns — TypeScript naming conventions]
- [Source: _bmad-output/implementation-artifacts/5-1-usage-metering-and-storage.md — previous story dev notes]
- [Source: gateway/api/dashboard.py:121-157 — GET /dashboard/usage endpoint]
- [Source: gateway/schemas/usage.py — DashboardUsageResponse, SubnetUsageWithQuota, UsageSummary, SubnetQuota]
- [Source: gateway/middleware/rate_limit.py:37-43 — _SUBNET_RATE_LIMITS with per-minute/day/month quotas]
- [Source: dashboard/src/hooks/useOverview.ts — TanStack Query hook pattern]
- [Source: dashboard/src/pages/Dashboard.tsx — Overview page layout pattern]
- [Source: dashboard/src/api/client.ts — openapi-fetch typed client]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Installed recharts (39 packages). Regenerated schema.d.ts from exported OpenAPI spec (no live server needed). Added 4 type re-exports to types/index.ts.
- Task 2: Created useUsage hook following useOverview pattern. TanStack Query with query key including all params for automatic refetch on change. 60s staleTime, 5min refetchInterval.
- Task 3: Created QuotaBar with 3 states (normal/warning/exceeded), progress bar with ARIA role, text labels always present alongside color (WCAG), subnet display names mapping.
- Task 4: Created RequestChart (AreaChart) and LatencyChart (LineChart). Both use ResponsiveContainer, accessibilityLayer, CartesianGrid with strokeDasharray. Tooltip with formatted dates/values. Legend for subnet toggle. Latency chart shows p50/p95/p99 with green/amber/red colors.
- Task 5: Created DateRangeSelector as button group with aria-pressed. Extracted getDateRange utility to separate file (date-range.ts) to satisfy ESLint react-refresh rule.
- Task 6: Replaced Usage placeholder with full page: quota bars with rate limits, date range selector, request volume chart, latency chart with subnet selector. Three-state rendering + empty state.
- Task 7: Created QuotaSummaryCard with QuotaBars and "View details" link. Added to Dashboard.tsx between QuickstartPanel and RateLimitsCard.
- Task 8: No frontend test framework configured. Validated via: TypeScript compilation (0 errors), Vite production build (success), ESLint (0 new errors, 4 pre-existing in ui/). 536 backend tests pass.

### Change Log

- 2026-03-14: Story 5.2 implementation complete — usage dashboard with Recharts charts, QuotaBar, date range selector, and quota summary on Overview page
- 2026-03-14: Code review #1 — 5 issues fixed (2 HIGH, 3 MEDIUM): extracted shared SUBNET_DISPLAY_NAMES/COLORS/RATE_LIMITS to subnet-constants.ts, used cn() instead of template literal in subnet selector, added error handling to QuotaSummaryCard, documented QuotaSummaryCard fetch trade-off

### File List

New files:
- dashboard/src/hooks/useUsage.ts — TanStack Query hook for GET /dashboard/usage
- dashboard/src/components/usage/QuotaBar.tsx — Quota progress bar with 3 visual states
- dashboard/src/components/usage/RequestChart.tsx — Recharts AreaChart for request volume
- dashboard/src/components/usage/LatencyChart.tsx — Recharts LineChart for p50/p95/p99 latency
- dashboard/src/components/usage/DateRangeSelector.tsx — 7d/30d/90d button group
- dashboard/src/components/usage/date-range.ts — DateRange type and getDateRange utility
- dashboard/src/components/usage/subnet-constants.ts — Shared subnet display names, colors, and rate limits
- dashboard/src/components/overview/QuotaSummaryCard.tsx — Quota bars on Overview page

Modified files:
- dashboard/src/api/schema.d.ts — regenerated with usage endpoint types
- dashboard/src/types/index.ts — added usage type re-exports
- dashboard/src/pages/Usage.tsx — replaced placeholder with full usage dashboard
- dashboard/src/pages/Dashboard.tsx — added QuotaSummaryCard import and component
- dashboard/package.json — added recharts dependency
- dashboard/package-lock.json — updated lockfile
