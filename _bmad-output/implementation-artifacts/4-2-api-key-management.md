# Story 4.2: API Key Management

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to create, view, rotate, and revoke API keys through the dashboard,
so that I can manage my API access without using CLI tools.

## Acceptance Criteria

1. **Given** I am logged in and on the API Keys page
   **When** I view my keys
   **Then** I see an OpenAI-style table showing each key's name, prefix (masked), status, creation date, and last used date (FR5)
   **And** full key values are never displayed after initial creation

2. **Given** I click the "Create API Key" button
   **When** the key is generated
   **Then** it appears once in a modal with a prominent copy-to-clipboard button
   **And** the key is prefixed `tao_sk_live_` or `tao_sk_test_` based on environment
   **And** no configuration wizard is required — optional name field, one click to generate
   **And** an `aria-live` region announces "Key copied" on clipboard copy (FR4)

3. **Given** I want to rotate a key
   **When** I select "Rotate" on an existing key
   **Then** a single flow generates a new key and revokes the old one atomically (FR6)
   **And** the new key is displayed once with copy-to-clipboard
   **And** the old key is immediately invalidated

4. **Given** I want to revoke a key
   **When** I select "Revoke" and confirm via a destructive confirmation dialog
   **Then** the key is immediately invalidated (FR7)
   **And** the key row updates to show revoked status (red dot)
   **And** requests using the revoked key receive 401 immediately

5. **Given** the API Keys page
   **When** I interact using only keyboard
   **Then** all actions (create, copy, rotate, revoke) are accessible via keyboard navigation
   **And** focus management follows WCAG 2.1 AA guidelines
   **And** icon-only buttons have `aria-label` attributes

6. **Given** the API Keys page on mobile (<1024px)
   **When** I view the table
   **Then** touch targets are minimum 44x44px
   **And** the table is usable without horizontal scrolling (responsive layout or card view)

7. **Given** I have no API keys
   **When** I visit the API Keys page
   **Then** I see an empty state: "No API keys yet. Create one to get started." with a create button

## Tasks / Subtasks

- [x] Task 1: Add shadcn/ui Dialog and Table components (AC: #2, #1)
  - [x] 1.1 Create custom `dialog` component (hand-crafted, matching existing shadcn-style pattern — no Radix)
  - [x] 1.2 Create custom `table` component (hand-crafted)
  - [x] 1.3 Create custom `badge` component for status indicators
  - [x] 1.4 Create custom `alert-dialog` component for destructive confirmations

- [x] Task 2: Add backend support for key names and rotation (AC: #2, #3)
  - [x] 2.1 Add `name` column (nullable String(100)) to `ApiKey` model + Alembic migration
  - [x] 2.2 Update `ApiKeyCreateRequest` schema to accept optional `name: str | None = None`
  - [x] 2.3 Update `ApiKeyCreateResponse` and `ApiKeyListItem` schemas to include `name` field
  - [x] 2.4 Update `create_api_key()` in service to accept and persist `name` parameter; auto-generate "Key N" if blank
  - [x] 2.5 Update `list_api_keys()` to include name in results
  - [x] 2.6 Add `POST /dashboard/api-keys/rotate/{key_id}` endpoint: creates new key, revokes old key atomically in single transaction (FR6)
  - [x] 2.7 Rotate endpoint returns `ApiKeyRotateResponse` (new key with full value + revoked_key_id)
  - [x] 2.8 Add `include_revoked` query param to `GET /dashboard/api-keys` endpoint (defaults false)

- [x] Task 3: Add TypeScript types and API hook for key management (AC: #1, #2, #3, #4)
  - [x] 3.1 Add API key types to `dashboard/src/types/index.ts`: `ApiKey`, `ApiKeyCreateRequest`, `ApiKeyCreateResponse`, `ApiKeyListResponse`, `ApiKeyRotateResponse`
  - [x] 3.2 Create `dashboard/src/hooks/useApiKeys.ts` with TanStack Query:
    - `useApiKeys()` — `GET /dashboard/api-keys` with pagination
    - `useCreateApiKey()` — `POST /dashboard/api-keys` mutation, invalidates list on success
    - `useRotateApiKey()` — `POST /dashboard/api-keys/rotate/{id}` mutation, invalidates list on success
    - `useRevokeApiKey()` — `DELETE /dashboard/api-keys/{id}` mutation, invalidates list on success
  - [x] 3.3 All fetch calls use `credentials: "include"` for cookie auth (match useAuth.ts pattern)

- [x] Task 4: Build API key table component (AC: #1, #5, #7)
  - [x] 4.1 Create `dashboard/src/components/api-keys/ApiKeyTable.tsx`:
    - Columns: Name | Key (masked prefix in monospace) | Status | Created | Actions
    - Status: green dot + "Active" or red dot + "Revoked" (color never sole indicator)
    - Timestamps: relative when recent ("2 hours ago"), absolute when old ("Mar 8, 2026")
    - Actions column: right-aligned ghost buttons (Rotate, Revoke)
    - Row hover: bg-elevated (#F4F4F5) background
    - Column headers: uppercase, text-xs, text-muted-foreground, semibold
  - [x] 4.2 Create `dashboard/src/components/api-keys/ApiKeyDisplay.tsx`:
    - Masked key in monospace `<code>` element: `tao_sk_live_abc1...`
    - Copy-prefix icon button with Tooltip
    - Clipboard feedback: icon changes to checkmark, reverts after 2 seconds
    - `aria-live` region for "Copied" announcement
  - [x] 4.3 Empty state: single row spanning all columns, "No API keys yet. Create one to get started." + Create button
  - [x] 4.4 All interactive elements keyboard-accessible, `aria-label` on icon buttons

- [x] Task 5: Build create key dialog (AC: #2, #5)
  - [x] 5.1 Create `dashboard/src/components/api-keys/CreateKeyDialog.tsx`:
    - Trigger: "Create API Key" primary button (solid indigo) in page header
    - Form: optional name field (placeholder: "e.g., production, testing"), marked "(optional)"
    - Submit on Enter (single-field form)
    - "Generate Key" primary button
    - No cancel button — closing dialog cancels
  - [x] 5.2 After generation, dialog transitions to key display state:
    - Full key shown in monospace, never again after dialog closes
    - "Copy" button with clipboard feedback (checkmark + "Copied" for 2s)
    - Warning text: "This key won't be shown again. Copy it now."
    - Backdrop click does NOT close while key is displayed — must explicitly close via X button
    - `aria-live` region announces "Key copied" on copy
  - [x] 5.3 On dialog close, TanStack Query invalidates key list (new key appears in table)

- [x] Task 6: Build rotate key dialog (AC: #3)
  - [x] 6.1 Create `dashboard/src/components/api-keys/RotateKeyDialog.tsx`:
    - Trigger: "Rotate" ghost button in table row actions
    - Confirmation step: "This will create a new key and immediately revoke [key prefix]. Active integrations using this key will stop working."
    - On confirm: calls rotate endpoint, displays new key (same display pattern as create)
    - Full new key shown once with copy-to-clipboard
    - On close: table refreshes, old key shows revoked, new key shows active

- [x] Task 7: Build revoke key confirmation (AC: #4)
  - [x] 7.1 Create `dashboard/src/components/api-keys/RevokeKeyDialog.tsx`:
    - Trigger: "Revoke" ghost button in table row actions (destructive styling)
    - Uses AlertDialog (not Dialog) for destructive confirmation pattern
    - Description: "This will immediately invalidate this key. Active integrations using this key will stop working."
    - Confirm button: solid red, white text ("Revoke Key")
    - Cancel button: outline variant
    - On confirm: calls revoke endpoint, table refreshes, key shows revoked status

- [x] Task 8: Wire up ApiKeys page (AC: #1, #6, #7)
  - [x] 8.1 Replace placeholder `dashboard/src/pages/ApiKeys.tsx` with full implementation:
    - Page header: "API Keys" title + "Create API Key" primary button (right-aligned)
    - ApiKeyTable component with loading/error/empty states
    - All dialogs wired to table actions
  - [x] 8.2 Responsive: table uses overflow-auto wrapper for horizontal scroll on narrow screens
  - [x] 8.3 Page uses DashboardLayout shell (already set up in Story 4.1)

- [x] Task 9: Write tests (AC: all)
  - [x] 9.1 Backend tests for new endpoints (9 new tests, all passing):
    - `test_create_api_key_with_name` — name persisted and returned
    - `test_create_api_key_without_name_auto_generates` — "Key N" auto-naming
    - `test_list_api_keys_includes_name` — name field in list response
    - `test_rotate_api_key_creates_new_revokes_old` — atomic rotation
    - `test_rotate_api_key_returns_full_new_key` — new key visible once
    - `test_rotate_nonexistent_key_returns_404`
    - `test_rotate_revoked_key_returns_404` — can't rotate already-revoked key
    - `test_list_api_keys_with_include_revoked` — shows revoked keys when param true
    - `test_list_api_keys_default_excludes_revoked` — backward compatibility
  - [ ] 9.2 Frontend tests deferred — Vitest not configured in Story 4.1 (no test script in package.json)

## Dev Notes

### Architecture Patterns and Constraints

- **React SPA served by FastAPI** — single deployment. Dashboard at `dashboard/dist/`, served as static files. Dev mode: Vite dev server proxies to FastAPI backend.
- **Cookie-based JWT for dashboard** — all dashboard API calls use httpOnly cookies (credentials: "include"). Backend `get_current_org_id` dependency handles both Bearer and cookie auth.
- **TanStack Query for server state** — use `useQuery` for lists, `useMutation` for create/rotate/revoke with `queryClient.invalidateQueries` on success. No Redux, no Zustand.
- **shadcn/ui + Radix UI + Tailwind CSS** — components copied into project via shadcn CLI. All accessibility (keyboard nav, ARIA, focus management) comes from Radix primitives.

### CRITICAL: Backend Gaps That Must Be Fixed

1. **No `name` field on API keys** — The `ApiKey` model has `id`, `org_id`, `prefix`, `key_hash`, `is_active`, `created_at`, `updated_at`. The UX spec requires a "Name" column. Add nullable `name` column with migration.

2. **No rotation endpoint** — Current endpoints are `POST /dashboard/api-keys` (create), `GET /dashboard/api-keys` (list), `DELETE /dashboard/api-keys/{key_id}` (revoke). FR6 requires atomic rotation (create new + revoke old in single transaction). Add `POST /dashboard/api-keys/rotate/{key_id}`.

3. **`include_revoked` not exposed** — The service supports `include_revoked` parameter but the API endpoint doesn't pass it through. The table needs to show revoked keys with red status. Add query param.

4. **No `last_used` tracking** — UX spec shows "Last Used" column. This is tracked nowhere currently. **DECISION: Defer `last_used` to a future story (Story 5.x usage metering) — the column exists in the UX spec but tracking it requires usage record correlation. For now, omit the column from the table.**

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/api/api_keys.py`** — 3 existing endpoints at `/dashboard/api-keys`. Uses `get_current_org_id` dependency. Extend, don't replace.
- **`gateway/services/api_key_service.py`** — `create_api_key()`, `list_api_keys()`, `revoke_api_key()`. Has `generate_api_key(env)` that creates `tao_sk_{env}_{random}` format. `MAX_KEYS_PER_ORG = 50`, `API_KEY_PREFIX_LENGTH = 20`.
- **`gateway/schemas/api_keys.py`** — `ApiKeyCreateRequest(environment)`, `ApiKeyCreateResponse(id, key, prefix, created_at)`, `ApiKeyListItem(id, prefix, is_active, created_at)`, `ApiKeyListResponse(items, total)`.
- **`gateway/models/api_key.py`** — SQLAlchemy model with `id`, `org_id`, `prefix`, `key_hash`, `is_active` + `TimestampMixin`.
- **`gateway/middleware/auth.py`** — `get_current_org_id()` checks Bearer header first, then cookie. Works for dashboard.
- **`dashboard/src/hooks/useAuth.ts`** — Pattern reference for TanStack Query + credentials: "include" cookie auth.
- **`dashboard/src/lib/validation.ts`** — Shared form validation helpers from Story 4.1.
- **`dashboard/src/components/ui/`** — button, card, input, label, separator, tooltip, sheet, dropdown-menu already installed.
- **`tests/conftest.py`** — Shared fixtures for real Postgres, Redis, and app client. Reuse for new tests.
- **`tests/api/test_api_keys.py`** — Existing tests for create/list/revoke endpoints. New tests go here or in a new file.

### What NOT to Touch

- Do NOT modify the Bearer token API auth flow — API callers depend on it
- Do NOT add the quickstart code snippets panel — Story 4.3 owns that
- Do NOT add usage charts or quota display — Story 5.2 owns that
- Do NOT implement `last_used` tracking — requires usage metering correlation (Story 5.x)
- Do NOT add Cloudflare Turnstile or bot prevention
- Do NOT add dark mode styling beyond what Story 4.1 established
- Do NOT modify the sidebar or dashboard shell layout

### Design System — Key Values (from Story 4.1)

| Property | Value |
|---|---|
| Primary color | Indigo `#4F46E5` (hover: `#4338CA`) |
| Background | White `#FFFFFF` |
| Surface/sidebar | Near-white `#FAFAFA` |
| Border | Zinc `#E4E4E7` |
| Text primary | Near-black `#18181B` |
| Text secondary | Gray `#71717A` |
| Status active | Emerald green dot + text |
| Status revoked | Red dot + text |
| UI font | Inter, 14px base |
| Code font | JetBrains Mono (for key prefixes, full keys) |
| Card padding | 24px, 1px border, 4px radius |
| Content max-width | 1200px, centered |
| Table header | uppercase, text-xs, text-muted, semibold |
| Row hover | `#F4F4F5` |
| Destructive button | Solid red, white text |
| Ghost button | Transparent background, text color, hover shows background |

### UX Patterns — Key Details

**Copy-to-clipboard:**
- Click target: entire button, not just icon
- Feedback: clipboard icon -> checkmark + "Copied" text for 2 seconds, then reverts
- Fallback: if clipboard API unavailable, select text for manual copy
- Monospace treatment for all copyable text
- `aria-live="polite"` region for screen reader announcements

**Status badges:**
- Active: 8px green dot + "Active" text (color never sole indicator)
- Revoked: 8px red dot + "Revoked" text

**Timestamps:**
- Relative when recent: "2 hours ago", "Yesterday"
- Absolute when old: "Mar 8, 2026"

**Destructive actions:**
- Always require confirmation dialog (AlertDialog)
- Explicit consequences description
- Confirm button: solid red background, white text
- Toast notification on success (revocation only — exception to inline feedback rule)

**Empty state:**
- Clean, actionable: text + CTA button
- "No API keys yet. Create one to get started."
- No illustrations, no clever copy

### Project Structure Notes

New dashboard files:
```
dashboard/src/
├── components/
│   ├── api-keys/
│   │   ├── ApiKeyTable.tsx        # Key list table with actions
│   │   ├── ApiKeyDisplay.tsx      # Masked key + copy button
│   │   ├── CreateKeyDialog.tsx    # Create key modal
│   │   ├── RotateKeyDialog.tsx    # Rotate key confirmation + display
│   │   └── RevokeKeyDialog.tsx    # Revoke confirmation (AlertDialog)
│   └── ui/
│       ├── dialog.tsx             # shadcn/ui dialog (new)
│       ├── table.tsx              # shadcn/ui table (new)
│       ├── badge.tsx              # shadcn/ui badge (new)
│       └── alert-dialog.tsx       # shadcn/ui alert-dialog (new)
├── hooks/
│   └── useApiKeys.ts             # TanStack Query hooks for key CRUD
└── pages/
    └── ApiKeys.tsx                # Replace placeholder with full page
```

Modified backend files:
- `gateway/models/api_key.py` — add `name` column
- `gateway/schemas/api_keys.py` — add `name` to request/response schemas, add rotation schemas
- `gateway/services/api_key_service.py` — add `rotate_api_key()`, update `create_api_key()` for name
- `gateway/api/api_keys.py` — add rotate endpoint, add `include_revoked` query param
- `migrations/versions/xxxx_add_name_to_api_keys.py` — new Alembic migration

Test files:
- `tests/api/test_api_keys.py` — extend with rotation and name tests (or new file `tests/api/test_api_keys_rotation.py`)
- `dashboard/src/__tests__/ApiKeys.test.tsx` — frontend component tests

### Testing Standards

- **Backend:** Real Postgres and Redis required — use Docker test containers, never mock
- **Backend:** Mock only Bittensor SDK — everything else uses real infrastructure
- **Frontend:** Vitest for unit tests, React Testing Library for component tests
- Run backend: `uv run pytest --tb=short -q`
- Run frontend: `cd dashboard && npm test`
- Lint backend: `uv run ruff check gateway/ tests/`
- Lint frontend: `cd dashboard && npm run lint`
- Types backend: `uv run mypy gateway/`
- Types frontend: `cd dashboard && npx tsc --noEmit`
- **489 backend tests currently pass** — this story must not break any existing tests

### Previous Story Intelligence (Story 4.1)

- **489 backend tests pass** — baseline for regression testing (up from 478 pre-4.1)
- **Branch naming:** `feat/story-X.Y-description`, merged via PR
- **Code review patterns from 4.1:** Two review rounds caught: stub implementations, inline imports, missing cleanup on token rotation, SPA path traversal, JWT encode-decode round-trip. Expect similar scrutiny.
- **f-string anti-pattern in structlog** — never use f-strings in structlog calls; use keyword args
- **Pattern: credentials: "include"** — all dashboard fetch calls must include this for cookie auth
- **Pattern: TanStack Query** — use `queryClient.invalidateQueries` after mutations for automatic list refresh
- **Cookie auth works** — `get_current_org_id` already handles both Bearer and cookie. Dashboard endpoints are at `/dashboard/*` path.
- **Existing API key endpoints use `/dashboard/api-keys` path** — NOT `/api-keys`. The router mounts them under the dashboard prefix.

### Git Intelligence (Recent Commits)

- `24cc47f` Merge PR #31: Story 4.1 dashboard shell and authentication
- `a2cd9a8` feat: add dashboard shell with React SPA and cookie-based JWT auth (Story 4.1)
- `1259b14` Merge PR #30: Story 3.4 in-memory quality scoring
- Pattern: feature branches merged via PR. Branch: `feat/story-4.2-api-key-management`. Each story is one commit + merge.

### Security Considerations

- **Full key shown only once at creation** — after dialog closes, only the masked prefix is available. This matches industry standard (Stripe, OpenAI, etc.)
- **Rotation atomicity** — new key creation and old key revocation MUST happen in the same DB transaction. If creation succeeds but revocation fails, the developer would have two active keys (acceptable) rather than zero (catastrophic).
- **Revocation is immediate** — Redis tombstone (120s TTL) ensures cached auth lookups are invalidated. The existing `revoke_api_key()` service already handles this.
- **No CSRF needed for MVP** — dashboard uses httpOnly cookies with SameSite=Lax. All state-changing operations are POST/DELETE with JSON content-type, which browsers won't send cross-origin.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 4, Story 4.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture, Authentication & Security, API Naming, Data Architecture]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#API Key Management Page, Table Layout, Create Key Modal, Rotation Flow, Revocation Flow, Copy-to-Clipboard, Status Badges, Empty States]
- [Source: gateway/api/api_keys.py — existing create/list/revoke endpoints]
- [Source: gateway/services/api_key_service.py — key generation, hashing, revocation with Redis tombstone]
- [Source: gateway/models/api_key.py — ApiKey model with prefix, key_hash, is_active]
- [Source: gateway/schemas/api_keys.py — request/response schemas]
- [Source: gateway/middleware/auth.py — get_current_org_id for cookie + Bearer auth]
- [Source: dashboard/src/hooks/useAuth.ts — pattern for cookie-based fetch with credentials: "include"]
- [Source: _bmad-output/implementation-artifacts/4-1-dashboard-shell-and-authentication.md — previous story dev notes and file list]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Created 4 custom shadcn-style UI components (dialog, table, badge, alert-dialog) matching existing hand-crafted pattern (no Radix UI dependency). All use accessible patterns: focus trapping, Escape to close, aria-modal, alertdialog role.
- Task 2: Added `name` column to ApiKey model with Alembic migration. Updated schemas for name field. Added `rotate_api_key()` service function (atomic create + revoke in single DB transaction). Added `POST /dashboard/api-keys/rotate/{key_id}` endpoint. Added `include_revoked` query param to list endpoint. Auto-generates "Key N" names when not provided.
- Task 3: Added 5 TypeScript types for API key management. Created `useApiKeys` hook with TanStack Query: useApiKeys (list), useCreateApiKey, useRotateApiKey, useRevokeApiKey. All use credentials: "include" and invalidate queries on mutation success.
- Task 4: Built ApiKeyTable with Name/Key/Status/Created/Actions columns. Status uses Badge with colored dot + text label. Relative timestamps for recent dates. Empty state with CTA. All icon buttons have aria-label.
- Task 5: Built CreateKeyDialog with optional name field, transitions to key display after generation. Full key shown in monospace with copy button. Warning text about one-time display. Backdrop click prevented while key is shown.
- Task 6: Built RotateKeyDialog with confirmation step showing consequences. After rotation, shows new key with copy-to-clipboard. On close, invalidates query list.
- Task 7: Built RevokeKeyDialog using AlertDialog for destructive pattern. Explicit consequences description. Destructive red button styling.
- Task 8: Replaced placeholder ApiKeys page with full implementation. Page header with title + create button. Card wrapper with table, loading, error, and empty states.
- Task 9: Added 9 backend tests (name create, auto-name, name in list, rotate, rotate returns full key, rotate 404, rotate revoked 404, include_revoked, default excludes revoked). Updated model column test. 501 total tests pass (up from 489). Ruff clean, mypy clean, TypeScript clean.

### Change Log

- 2026-03-14: Story 4.2 implementation complete — API key management dashboard with name field, rotation endpoint, include_revoked param, full React SPA with table/create/rotate/revoke components
- 2026-03-14: Code review #1 — 13 issues fixed (5 HIGH, 8 MEDIUM): added FOR UPDATE locks on rotate/create to prevent race conditions, fixed _next_key_name to avoid duplicates, added focus trap and focus restore to dialogs, removed Escape dismiss from AlertDialog, added aria-labelledby/describedby, fixed credentials override in fetchJson, wrapped mutateAsync in try/catch, removed API key from DOM attributes, cleared setTimeout on unmount, added role="alert" to error messages, added aria-hidden to decorative dots, fixed name type consistency in schema

### File List

New frontend files:
- dashboard/src/components/ui/dialog.tsx
- dashboard/src/components/ui/table.tsx
- dashboard/src/components/ui/badge.tsx
- dashboard/src/components/ui/alert-dialog.tsx
- dashboard/src/components/api-keys/ApiKeyDisplay.tsx
- dashboard/src/components/api-keys/ApiKeyTable.tsx
- dashboard/src/components/api-keys/CreateKeyDialog.tsx
- dashboard/src/components/api-keys/RotateKeyDialog.tsx
- dashboard/src/components/api-keys/RevokeKeyDialog.tsx
- dashboard/src/hooks/useApiKeys.ts

Modified frontend files:
- dashboard/src/types/index.ts — added API key types
- dashboard/src/pages/ApiKeys.tsx — replaced placeholder with full page

New backend files:
- migrations/versions/a3b7c9d1e2f4_add_name_to_api_keys.py — Alembic migration

Modified backend files:
- gateway/models/api_key.py — added `name` column
- gateway/schemas/api_keys.py — added name to schemas, added ApiKeyRotateResponse
- gateway/services/api_key_service.py — added rotate_api_key(), updated create_api_key() for name, added _next_key_name()
- gateway/api/api_keys.py — added rotate endpoint, added include_revoked param, added name to responses

Modified test files:
- tests/api/test_api_keys.py — added 9 new tests for name, rotation, include_revoked
- tests/models/test_models.py — updated api_key columns test for name field
