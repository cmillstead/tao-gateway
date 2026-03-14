# Story 4.3: Account Overview & Quickstart

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to see my account status and a quickstart guide with my API key pre-filled,
so that I can understand my tier, see available capabilities, and make my first API call quickly.

## Acceptance Criteria

1. **Given** I am logged in and on the Overview page
   **When** the page loads
   **Then** I see my account overview including current tier status (free/paid) (FR3)
   **And** available capabilities displayed as "Text Generation," "Image Generation," "Code Generation" — not SN1/SN19/SN62
   **And** each capability shows a health status indicator (green/yellow/red with text label — color is never the sole indicator)

2. **Given** I have created at least one API key
   **When** I view the quickstart panel
   **Then** I see working code snippets (curl and Python tabs) with my actual API key prefix pre-filled
   **And** each snippet has a copy-to-clipboard button
   **And** the Python example shows an OpenAI client `base_url` swap pattern

3. **Given** I have not created any API keys yet
   **When** I view the Overview page
   **Then** the quickstart panel prompts me to create a key first
   **And** a direct link/button navigates to the API Keys page

4. **Given** the Overview page
   **When** I check quota consumption
   **Then** I see per-subnet quota usage as progress bars or counters (e.g., "847 / 1,000 requests used")
   **And** the information is answerable at a glance without clicking

5. **Given** the page loads
   **When** measuring performance
   **Then** the page loads in under 2 seconds (NFR6)

## Tasks / Subtasks

- [x] Task 1: Add backend endpoint for account overview data (AC: #1, #4)
  - [x]1.1 Create `GET /dashboard/overview` endpoint in `gateway/api/dashboard.py` (new file)
  - [x]1.2 Create `OverviewResponse` schema in `gateway/schemas/dashboard.py` (new file) with:
    - `email: str`
    - `tier: str` (always "free" for MVP — no paid tier yet)
    - `created_at: datetime`
    - `api_key_count: int`
    - `subnets: list[SubnetOverview]` (capability name, netuid, health status, rate limits)
  - [x]1.3 Create `SubnetOverview` schema: `name: str`, `netuid: int`, `status: str` (healthy/degraded/unavailable), `rate_limits: dict` (minute/day/month limits)
  - [x]1.4 Wire the endpoint to read from:
    - `AdapterRegistry.list_all()` for registered subnets + configs
    - `MetagraphManager.get_all_states()` for health status (reuse health.py pattern)
    - `get_subnet_rate_limits()` for per-subnet limits
    - DB query for org's API key count
  - [x]1.5 Register new router in `gateway/api/router.py` under `/dashboard` prefix

- [x] Task 2: Add frontend types and API hook (AC: #1, #2, #4)
  - [x]2.1 Add `OverviewData`, `SubnetOverview` types to `dashboard/src/types/index.ts`
  - [x]2.2 Create `dashboard/src/hooks/useOverview.ts` with TanStack Query:
    - `useOverview()` — `GET /dashboard/overview` with `credentials: "include"`
  - [x]2.3 Extend `useApiKeys` hook (or create `useFirstApiKey()`) to get the most recent active key prefix for quickstart snippets

- [x] Task 3: Build MetricCard component (AC: #1)
  - [x]3.1 Create `dashboard/src/components/overview/MetricCard.tsx`:
    - Label (text-sm, text-muted-foreground), value (text-2xl, font-semibold), optional subtitle
    - Uses existing Card component
    - Optional click handler for drill-down navigation
  - [x]3.2 Three cards on Overview: "Current Tier" (Free), "Active Keys" (count), "Capabilities" (3 subnets)

- [x] Task 4: Build SubnetStatusBadge component (AC: #1)
  - [x]4.1 Create `dashboard/src/components/overview/SubnetStatusBadge.tsx`:
    - Shows capability name + health status dot + text label
    - Healthy: green dot + "Healthy", Degraded: amber dot + "Degraded", Down: red dot + "Down"
    - Color is never the sole indicator — always paired with text

- [x] Task 5: Build capabilities/health section (AC: #1)
  - [x]5.1 Create `dashboard/src/components/overview/CapabilitiesCard.tsx`:
    - Card with three rows: "Text Generation (SN1)", "Image Generation (SN19)", "Code Generation (SN62)"
    - Each row shows SubnetStatusBadge for health status
    - Maps netuid to human-readable capability name

- [x] Task 6: Build QuotaBar component (AC: #4)
  - [x]6.1 Create `dashboard/src/components/overview/QuotaBar.tsx`:
    - Progress bar with label and counts: "Text Generation — 847 / 1,000 monthly"
    - Normal (<80%): indigo fill
    - Warning (80-99%): amber fill
    - Exceeded (100%): red fill + "Quota exceeded" text
    - Color is never sole indicator — explicit numbers always shown
  - [x]6.2 Note: Actual usage counts require usage metering (Story 5.1). For now, show the rate limits only (e.g., "10 req/min, 100/day, 1,000/month") as static quota info. Actual consumption tracking deferred to Story 5.1/5.2.

- [x] Task 7: Build CodeSnippet / Quickstart panel (AC: #2, #3)
  - [x]7.1 Create `dashboard/src/components/overview/CodeSnippet.tsx`:
    - Dark background (`#1E293B`) code block with monospace font (JetBrains Mono)
    - Copy-to-clipboard button with feedback (checkmark + "Copied" for 2s)
    - API key prefix auto-filled in the snippet (use first active key's prefix as placeholder, with `<YOUR_API_KEY>` fallback)
  - [x]7.2 Create `dashboard/src/components/overview/QuickstartPanel.tsx`:
    - Tab bar: "curl" | "Python" tabs
    - curl tab: `curl -X POST https://api.taogateway.com/v1/chat/completions -H "Authorization: Bearer <key>" -H "Content-Type: application/json" -d '{"model": "tao-text", "messages": [{"role": "user", "content": "Hello"}]}'`
    - Python tab: OpenAI client with `base_url` swap pattern:
      ```python
      from openai import OpenAI
      client = OpenAI(base_url="https://api.taogateway.com/v1", api_key="<key>")
      response = client.chat.completions.create(model="tao-text", messages=[{"role": "user", "content": "Hello"}])
      print(response.choices[0].message.content)
      ```
    - Empty state when no API keys: "Create an API key to see quickstart examples" + link to API Keys page
  - [x]7.3 Add custom `tabs` UI component to `dashboard/src/components/ui/tabs.tsx` (hand-crafted, matching existing shadcn-style pattern — no Radix dependency)

- [x] Task 8: Wire up Dashboard/Overview page (AC: #1-5)
  - [x]8.1 Replace placeholder in `dashboard/src/pages/Dashboard.tsx` with full implementation:
    - Page header: "Overview" title
    - Metric cards row (3 cards)
    - Capabilities/health card
    - Quickstart panel (with tabs)
    - Quota information section (rate limits per subnet)
  - [x]8.2 Use DashboardLayout shell (already set up in Story 4.1)
  - [x]8.3 Loading state: skeleton placeholders matching content layout
  - [x]8.4 Error state: inline error banner at top of content area

- [x] Task 9: Write tests (AC: all)
  - [x]9.1 Backend tests for `GET /dashboard/overview`:
    - Returns tier, email, key count, subnet info
    - Returns correct health status from metagraph state
    - Returns rate limits per subnet
    - Requires authentication (401 without cookie)
  - [x]9.2 Frontend tests deferred — Vitest not configured (same as Story 4.2)

## Dev Notes

### Architecture Patterns and Constraints

- **React SPA served by FastAPI** — single deployment. Dashboard at `dashboard/dist/`, served as static files. Dev mode: Vite dev server proxies to FastAPI backend.
- **Cookie-based JWT for dashboard** — all dashboard API calls use httpOnly cookies (`credentials: "include"`). Backend `get_current_org_id` dependency handles both Bearer and cookie auth.
- **TanStack Query for server state** — use `useQuery` for data fetching with `queryClient.invalidateQueries` on mutations. No Redux, no Zustand.
- **shadcn/ui components are hand-crafted** — Story 4.2 established that UI components are hand-written in shadcn style (no Radix UI dependency). Follow this pattern for new components (tabs).
- **structlog for logging** — never use f-strings in structlog calls; use keyword args.

### CRITICAL: Understanding Data Availability for MVP

1. **Tier is always "free"** — No paid tier exists until Stripe integration (Phase 2). The tier display is hardcoded to "Free" with a future upgrade path placeholder.

2. **Quota usage tracking does NOT exist yet** — Story 5.1 implements usage metering. The overview page should show **rate limits** (what the limits ARE) but cannot show **current consumption** (how much has been used). Display limits as informational cards, not progress bars with actual usage.

3. **Subnet health IS available** — via `MetagraphManager.get_all_states()`. Reuse the pattern from `gateway/api/health.py:_get_metagraph_status()`.

4. **API key count IS available** — simple DB count query on `ApiKey` model where `org_id` matches and `is_active = True`.

5. **API key prefix for quickstart** — use the first active key's prefix. The full key is never stored (only hash). Show `tao_sk_live_...` prefix in snippets as a visual indicator — the developer must use their actual key (copied at creation time).

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/api/health.py`** — `_get_metagraph_status()` function. Extract subnet health derivation logic and reuse. Status mapping: `metagraph is None` → unavailable, `is_stale` → degraded, else → healthy.
- **`gateway/middleware/rate_limit.py`** — `get_subnet_rate_limits(netuid)` returns `{"minute": N, "day": N, "month": N}`. `_SUBNET_RATE_LIMITS` dict has limits for netuids 1, 19, 62.
- **`gateway/subnets/registry.py`** — `AdapterRegistry.list_all()` returns `AdapterInfo` with config (netuid, subnet_name) and model_names.
- **`gateway/models/api_key.py`** — `ApiKey` model with `org_id`, `is_active`, `prefix` fields. Count active keys with simple query.
- **`gateway/middleware/auth.py`** — `get_current_org_id()` dependency for cookie auth. Use this on new dashboard endpoint.
- **`gateway/api/api_keys.py`** — Existing endpoints at `/dashboard/api-keys`. Pattern reference for new dashboard endpoint.
- **`gateway/schemas/api_keys.py`** — Pattern reference for new schema file.
- **`dashboard/src/hooks/useApiKeys.ts`** — Pattern reference for new hook (TanStack Query + credentials: "include").
- **`dashboard/src/hooks/useAuth.ts`** — Pattern reference for cookie-based fetch.
- **`dashboard/src/components/ui/`** — button, card, input, label, separator, tooltip, sheet, dropdown-menu, dialog, table, badge, alert-dialog already exist.
- **`dashboard/src/components/api-keys/ApiKeyDisplay.tsx`** — Copy-to-clipboard pattern. Reuse the same clipboard feedback pattern for code snippets.
- **`tests/conftest.py`** — Shared fixtures for real Postgres, Redis, and app client.

### What NOT to Touch

- Do NOT modify the Bearer token API auth flow — API callers depend on it
- Do NOT add usage charts or actual consumption tracking — Story 5.1/5.2 owns that
- Do NOT add Recharts or any charting library — no charts needed for this story (usage charts are Story 5.2)
- Do NOT add password reset or settings functionality — Story 4.5 / separate story
- Do NOT modify the sidebar or dashboard shell layout (Story 4.1 owns that)
- Do NOT add API client generation or build pipeline changes — Story 4.4 owns that
- Do NOT add dark mode styling beyond what Story 4.1 established
- Do NOT add Cloudflare Turnstile or bot prevention
- Do NOT try to show "requests used today" — usage metering doesn't exist yet (Story 5.1)
- Do NOT add admin/operator views — Epic 6 owns that

### Design System — Key Values (from Story 4.1/4.2)

| Property | Value |
|---|---|
| Primary color | Indigo `#4F46E5` (hover: `#4338CA`) |
| Background | White `#FFFFFF` |
| Surface/sidebar | Near-white `#FAFAFA` |
| Border | Zinc `#E4E4E7` |
| Text primary | Near-black `#18181B` |
| Text secondary | Gray `#71717A` |
| Status healthy | Green dot + text |
| Status degraded | Amber dot + text |
| Status down/unavailable | Red dot + text |
| UI font | Inter, 14px base |
| Code font | JetBrains Mono (for key prefixes, code snippets) |
| Card padding | 24px, 1px border, 4px radius |
| Content max-width | 1200px, centered |
| Code block background | Dark slate `#1E293B` |
| Metric card | Label (text-sm muted), value (text-2xl semibold), subtitle |

### UX Patterns — Key Details

**Subnet-as-capability framing:**
- SN1 → "Text Generation"
- SN19 → "Image Generation"
- SN62 → "Code Generation"
- Show subnet ID as secondary detail in parentheses: "Text Generation (SN1)"
- Priya ignores the parenthetical; Kai uses it

**Quickstart snippets:**
- Dark code block (`#1E293B`) with light text
- Tab bar for language switching (curl / Python)
- Copy button per snippet with clipboard feedback
- Key placeholder uses first active key's prefix as indicator, but tells user to use their full key
- If no keys: empty state with CTA to API Keys page

**Metric cards:**
- Card with Label (small, muted) → Value (large, bold) → optional Subtitle
- Three cards: Tier, Active Keys, Capabilities count
- Clean, no-fuss layout — answer "what's my account status?" at a glance

**Quota/rate limit display:**
- Per-subnet rate limits displayed as simple text: "10 req/min · 100/day · 1,000/month"
- No progress bars yet (need usage metering for actual consumption)
- Future: Story 5.2 will add QuotaBar with actual usage vs. limit

**Health status:**
- Derive from metagraph state (same logic as `/v1/health`)
- Green dot + "Healthy" = metagraph synced, miners available
- Amber dot + "Degraded" = metagraph stale
- Red dot + "Down" = no metagraph data

### Project Structure Notes

New dashboard files:
```
dashboard/src/
├── components/
│   ├── overview/
│   │   ├── MetricCard.tsx          # Single metric display card
│   │   ├── SubnetStatusBadge.tsx   # Health status dot + text
│   │   ├── CapabilitiesCard.tsx    # Subnet capabilities with health
│   │   ├── QuickstartPanel.tsx     # Tabbed code snippets
│   │   └── CodeSnippet.tsx         # Dark code block with copy
│   └── ui/
│       └── tabs.tsx                # shadcn-style tabs (new)
└── hooks/
    └── useOverview.ts              # TanStack Query hook for overview data
```

Modified dashboard files:
- `dashboard/src/pages/Dashboard.tsx` — replace placeholder with full overview page
- `dashboard/src/types/index.ts` — add overview types

New backend files:
- `gateway/api/dashboard.py` — `GET /dashboard/overview` endpoint
- `gateway/schemas/dashboard.py` — `OverviewResponse`, `SubnetOverview` schemas

Modified backend files:
- `gateway/api/router.py` — register new dashboard router

Test files:
- `tests/api/test_dashboard.py` — overview endpoint tests

### Testing Standards

- **Backend:** Real Postgres and Redis required — use Docker test containers, never mock
- **Backend:** Mock only Bittensor SDK — everything else uses real infrastructure
- Run backend: `uv run pytest --tb=short -q`
- Lint backend: `uv run ruff check gateway/ tests/`
- Types backend: `uv run mypy gateway/`
- Types frontend: `cd dashboard && npx tsc --noEmit`
- **501 backend tests currently pass** — this story must not break any existing tests

### Previous Story Intelligence (Story 4.2)

- **501 backend tests pass** — baseline for regression testing (up from 489 pre-4.2)
- **Branch naming:** `feat/story-X.Y-description`, merged via PR
- **Code review patterns from 4.2:** Two review rounds caught: race conditions on rotate/create (added FOR UPDATE locks), missing focus trap/restore on dialogs, missing aria-labelledby/describedby, credentials override in fetchJson, API key exposed in DOM attributes, setTimeout not cleaned up on unmount. Expect similar scrutiny.
- **Hand-crafted UI components** — Story 4.2 established that all UI components (dialog, table, badge, alert-dialog) are hand-written matching shadcn patterns, NOT installed via shadcn CLI or Radix. The tabs component for this story MUST follow the same pattern.
- **f-string anti-pattern in structlog** — never use f-strings in structlog calls; use keyword args
- **Pattern: credentials: "include"** — all dashboard fetch calls must include this for cookie auth
- **Pattern: TanStack Query** — use `queryClient.invalidateQueries` after mutations for automatic list refresh
- **Cookie auth works** — `get_current_org_id` already handles both Bearer and cookie auth
- **Existing dashboard endpoints use `/dashboard/*` path** — NOT root path
- **Auto-naming pattern** — Story 4.2 added auto-naming for API keys ("Key N"). Good pattern for developer-friendly defaults.

### Git Intelligence (Recent Commits)

- `deaba2d` feat: add API key management dashboard with rotation, naming, and code quality fixes (Story 4.2) (#32)
- `24cc47f` Merge PR #31: Story 4.1 dashboard shell and authentication
- `a2cd9a8` feat: add dashboard shell with React SPA and cookie-based JWT auth (Story 4.1)
- Pattern: feature branches merged via PR. Branch: `feat/story-4.3-account-overview-and-quickstart`.

### Security Considerations

- **No sensitive data exposed** — Overview endpoint returns org email, tier (free), key count, and subnet info. No passwords, no full API keys, no wallet data.
- **Key prefix in quickstart** — Only the masked prefix (`tao_sk_live_abc1...`) appears in snippets, never the full key. The full key is only shown once at creation time (Story 4.2).
- **Authentication required** — `GET /dashboard/overview` must use `get_current_org_id` dependency (cookie auth).
- **Rate limit info is not sensitive** — Free tier limits are public knowledge (documented in API docs). Safe to display.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 4, Story 4.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture, Authentication & Security, API Naming]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Overview Dashboard, Quickstart Panel, MetricCard, SubnetStatusBadge, CodeSnippet, QuotaBar]
- [Source: _bmad-output/planning-artifacts/prd.md#FR3 (account overview), FR19 (quota display)]
- [Source: gateway/api/health.py — _get_metagraph_status() for health derivation pattern]
- [Source: gateway/middleware/rate_limit.py — get_subnet_rate_limits(), _SUBNET_RATE_LIMITS]
- [Source: gateway/subnets/registry.py — AdapterRegistry.list_all() for subnet enumeration]
- [Source: gateway/models/api_key.py — ApiKey model for key count query]
- [Source: gateway/middleware/auth.py — get_current_org_id for cookie auth]
- [Source: dashboard/src/hooks/useApiKeys.ts — TanStack Query pattern reference]
- [Source: dashboard/src/components/api-keys/ApiKeyDisplay.tsx — clipboard feedback pattern]
- [Source: _bmad-output/implementation-artifacts/4-2-api-key-management.md — previous story dev notes]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Created `GET /dashboard/overview` endpoint with `OverviewResponse` and `SubnetOverview` Pydantic schemas. Endpoint returns org email, tier ("free"), active API key count, first key prefix, and per-subnet info (name, netuid, health status, rate limits). Health status derived from MetagraphManager state (same pattern as health.py). Rate limits from `get_subnet_rate_limits()`. Registered in router under `/dashboard` prefix.
- Task 2: Added `OverviewData`, `SubnetOverview`, `SubnetRateLimits` TypeScript types. Created `useOverview` hook with TanStack Query, `credentials: "include"` for cookie auth.
- Task 3: Created `MetricCard` component using existing Card UI. Supports label, value, subtitle, and optional click handler with proper focus styling.
- Task 4: Created `SubnetStatusBadge` component with colored dot + text label pattern. Healthy (green), Degraded (amber), Down (red). Color never sole indicator.
- Task 5: Created `CapabilitiesCard` showing three subnets with human-readable names ("Text Generation (SN1)") and health status badges.
- Task 6: Created `RateLimitsCard` showing per-subnet rate limits as text ("10 req/min · 100/day · 1,000/month"). No progress bars since usage metering doesn't exist yet (Story 5.1).
- Task 7: Created hand-crafted `Tabs` UI component (no Radix). Created `CodeSnippet` with dark code block and copy-to-clipboard. Created `QuickstartPanel` with curl/Python tabs, API key prefix pre-filled. Empty state when no keys with CTA to API Keys page.
- Task 8: Replaced placeholder Dashboard.tsx with full overview page: metric cards row (tier, active keys, subnets), capabilities card with health, quickstart panel, rate limits card. Loading skeleton and error states included.
- Task 9: Added 6 backend tests (account info, subnets, health status, rate limits, auth required, key count + prefix). 510 total tests pass (up from 501). Ruff clean, mypy clean, TypeScript clean. Dashboard builds successfully.

### Change Log

- 2026-03-14: Story 4.3 implementation complete — Account overview dashboard with tier display, subnet capabilities/health, quickstart panel with curl/Python snippets, rate limits display
- 2026-03-14: Code review #1 — 8 issues fixed (2 HIGH, 4 MEDIUM, 2 LOW): moved inline import to module level, deduplicated subnet iteration logic, added Literal type to SubnetOverview.status, replaced querySelector with useRef in CodeSnippet, extracted shared fetchJson to lib/api.ts, fixed MetricCard clickable area covering full card, fixed TabsContent to use hidden attribute for accessibility, extracted hardcoded API base URL to constant

### File List

New frontend files:
- dashboard/src/components/overview/MetricCard.tsx
- dashboard/src/components/overview/SubnetStatusBadge.tsx
- dashboard/src/components/overview/CapabilitiesCard.tsx
- dashboard/src/components/overview/RateLimitsCard.tsx
- dashboard/src/components/overview/CodeSnippet.tsx
- dashboard/src/components/overview/QuickstartPanel.tsx
- dashboard/src/components/ui/tabs.tsx
- dashboard/src/hooks/useOverview.ts
- dashboard/src/lib/api.ts — shared fetchJson utility

Modified frontend files:
- dashboard/src/pages/Dashboard.tsx — replaced placeholder with full overview page
- dashboard/src/types/index.ts — added overview types
- dashboard/src/hooks/useApiKeys.ts — use shared fetchJson from lib/api.ts

New backend files:
- gateway/api/dashboard.py — GET /dashboard/overview endpoint
- gateway/schemas/dashboard.py — OverviewResponse, SubnetOverview schemas

Modified backend files:
- gateway/api/router.py — registered dashboard router

New test files:
- tests/api/test_dashboard.py — 6 overview endpoint tests
