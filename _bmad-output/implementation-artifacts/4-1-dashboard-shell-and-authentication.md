# Story 4.1: Dashboard Shell & Authentication

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to sign up and log in to a polished web dashboard,
so that I can manage my TaoGateway account through a familiar, professional interface.

## Acceptance Criteria

1. **Given** I am a new user
   **When** I navigate to the dashboard signup page
   **Then** I see a minimal signup form (email, password)
   **And** on successful submission, my account is created and I am logged in automatically

2. **Given** I have an account
   **When** I submit the login form with valid credentials
   **Then** a JWT is set as an httpOnly cookie (15-30 min expiry) with a refresh token
   **And** I am redirected to the dashboard overview page (FR2)

3. **Given** I am logged in
   **When** I view the dashboard on a desktop (>=1280px)
   **Then** I see a full 240px left sidebar with grouped navigation (Overview, API Keys, Usage, Settings)
   **And** the layout follows Stripe/OpenAI-inspired professional design language

4. **Given** I am on a small desktop or tablet landscape (1024-1279px)
   **When** I view the dashboard
   **Then** the sidebar collapses to 64px icon-only mode with hover tooltips
   **And** main content expands to fill available width

5. **Given** I am on a tablet portrait or mobile (<1024px)
   **When** I view the dashboard
   **Then** the sidebar is hidden, accessible via a hamburger menu (Sheet component)
   **And** touch targets are minimum 44x44px

6. **Given** the dashboard HTML structure
   **When** I inspect the page
   **Then** it uses semantic elements (`<nav>`, `<main>`, `<header>`)
   **And** a skip link is present (hidden, visible on focus, jumps to main content)
   **And** all interactive components support keyboard navigation via Radix primitives

7. **Given** my JWT expires
   **When** I make a dashboard request
   **Then** the refresh token silently obtains a new JWT
   **And** I am not redirected to login unless the refresh token is also expired

## Tasks / Subtasks

- [x] Task 1: Initialize React SPA with Vite + TypeScript (AC: #3)
  - [x] 1.1 Create Vite project in `dashboard/` with React + TypeScript template
  - [x] 1.2 Install and configure Tailwind CSS v4
  - [x] 1.3 Initialize shadcn/ui with default theme + Indigo primary color override
  - [x] 1.4 Install required shadcn/ui components: Button, Card, Input, Label, Sheet, Separator, Tooltip, DropdownMenu
  - [x] 1.5 Install TanStack Query + React Router
  - [x] 1.6 Configure Vite proxy for `/auth/*`, `/dashboard/*`, `/v1/*` to backend during dev
  - [x] 1.7 Add Inter font (via Fontsource or CDN) and JetBrains Mono for code

- [x] Task 2: Add backend cookie-based JWT auth for dashboard (AC: #2, #7)
  - [x] 2.1 Add `POST /auth/login/dashboard` endpoint that sets JWT as httpOnly cookie (`Set-Cookie: access_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1800`)
  - [x] 2.2 Add refresh token model: `RefreshToken` table with `token_hash`, `org_id`, `expires_at`, `revoked_at`
  - [x] 2.3 Add `POST /auth/refresh` endpoint: validate refresh token cookie, issue new JWT cookie + new refresh token
  - [x] 2.4 Add `POST /auth/logout` endpoint: revoke refresh token, clear cookies
  - [x] 2.5 Update `get_current_org_id()` in `middleware/auth.py` to check both Bearer header (API) and cookie (dashboard) — Bearer takes priority
  - [x] 2.6 Ensure existing Bearer-based auth continues to work for API callers
  - [x] 2.7 Add Alembic migration for `refresh_tokens` table
  - [x] 2.8 Add `refresh_token_expire_days: int = 7` to Settings

- [x] Task 3: Build authentication pages (AC: #1, #2)
  - [x] 3.1 Create `pages/Login.tsx` — email + password form using shadcn Input, Label, Button
  - [x] 3.2 Create `pages/Signup.tsx` — email + password form, "Create Account" primary button
  - [x] 3.3 Implement form validation: field-level errors on submit (not keystroke), email format, password min 8 chars
  - [x] 3.4 On signup success: auto-login by calling `/auth/login/dashboard` immediately
  - [x] 3.5 On login success: redirect to `/dashboard` (overview page)
  - [x] 3.6 Style: centered card on white/near-white background, max-width 400px, professional minimalism

- [x] Task 4: Build dashboard shell layout (AC: #3, #4, #5, #6)
  - [x] 4.1 Create `components/layout/DashboardLayout.tsx` — sidebar + main content area wrapper
  - [x] 4.2 Create `components/layout/Sidebar.tsx` — 240px fixed, `#FAFAFA` background, navigation groups:
    - Group 1: Overview, API Keys, Usage (separated by Separator)
    - Group 2: Settings
    - Group 3: Docs (external link with arrow icon, opens new tab)
    - User menu at bottom: avatar + email + dropdown (Settings, Sign Out)
  - [x] 4.3 Implement responsive sidebar behavior:
    - `>=1280px` (`xl:`): Full 240px sidebar
    - `1024-1279px` (`lg:`): Collapsed 64px icon-only with Tooltip on hover
    - `<1024px`: Hidden, accessible via hamburger button + Sheet component
  - [x] 4.4 Add semantic HTML: `<nav aria-label="Main navigation">`, `<main id="main">`, `<header>`
  - [x] 4.5 Add skip link: hidden `<a href="#main">Skip to main content</a>`, visible on focus
  - [x] 4.6 Main content: scrollable, max-width 1200px, centered with auto margins
  - [x] 4.7 Page header: page title (h1) + optional primary action button (right-aligned)

- [x] Task 5: Implement auth context and route protection (AC: #7)
  - [x] 5.1 Create `hooks/useAuth.ts` — auth state management:
    - `user: { id, email } | null` (derived from JWT payload, decoded client-side for display only — auth is server-validated via cookie)
    - `isAuthenticated: boolean`
    - `login(email, password)` — calls `/auth/login/dashboard`
    - `signup(email, password)` — calls `/auth/signup` then auto-login
    - `logout()` — calls `/auth/logout`, clear state, redirect to login
  - [x] 5.2 Create `components/auth/ProtectedRoute.tsx` — wraps dashboard routes, redirects to login if not authenticated
  - [x] 5.3 Configure TanStack Query global `onError` to detect 401 responses and trigger silent refresh via `/auth/refresh`; if refresh fails, redirect to login
  - [x] 5.4 Add request interceptor: on 401, attempt one refresh, then retry the original request; if refresh also fails, redirect to login

- [x] Task 6: Set up routing and static serving (AC: #3)
  - [x] 6.1 Configure React Router with routes:
    - `/login` — Login page (public)
    - `/signup` — Signup page (public)
    - `/dashboard` — Overview page (protected, placeholder for Story 4.3)
    - `/dashboard/api-keys` — API Keys page (protected, placeholder for Story 4.2)
    - `/dashboard/usage` — Usage page (protected, placeholder for Story 5.2)
    - `/dashboard/settings` — Settings page (protected, placeholder)
  - [x] 6.2 Add placeholder pages for protected routes: title + "Coming soon" message
  - [x] 6.3 Configure FastAPI to serve dashboard static build from `dashboard/dist/`
  - [x] 6.4 Add catch-all fallback route for SPA client-side routing (serve `index.html` for all non-API paths)
  - [x] 6.5 Update `gateway/main.py` to mount static files (conditional on `dashboard/dist/` existing)

- [x] Task 7: Write tests (AC: all)
  - [x] 7.1 Backend tests for cookie-based auth:
    - `test_login_dashboard_sets_httponly_cookie` — verify Set-Cookie header
    - `test_refresh_token_issues_new_jwt` — verify refresh flow
    - `test_refresh_token_invalid_returns_401` — expired/revoked refresh
    - `test_logout_clears_cookies` — verify cookie deletion
    - `test_bearer_auth_still_works` — existing Bearer flow unchanged
    - `test_cookie_auth_on_dashboard_endpoints` — dashboard API works with cookie
  - [x] 7.2 Backend tests for static file serving:
    - `test_spa_fallback_serves_index_html` — non-API paths return index.html
    - `test_api_routes_not_caught_by_fallback` — `/v1/*`, `/auth/*` not affected
  - [x] 7.3 Frontend tests (Vitest):
    - `test_login_form_validates_email` — invalid email shows error
    - `test_login_form_validates_password_length` — < 8 chars shows error
    - `test_protected_route_redirects_unauthenticated` — redirect to /login
    - `test_sidebar_navigation_active_state` — correct item highlighted
    - `test_responsive_sidebar_collapse` — verify breakpoint behavior

## Dev Notes

### Architecture Patterns and Constraints

- **React SPA served by FastAPI** — single deployment, no separate frontend service. Dashboard built with Vite, output to `dashboard/dist/`, mounted as static files by FastAPI. In dev, Vite dev server proxies API calls to FastAPI.
- **shadcn/ui + Radix UI + Tailwind CSS** — components copied into project (not npm dependency). Use shadcn CLI to add components. All accessibility (keyboard nav, ARIA, focus management) comes from Radix primitives.
- **Cookie-based JWT for dashboard** — architecture doc specifies httpOnly cookies for dashboard auth, Bearer tokens for API auth. Current backend only implements Bearer. This story MUST add cookie-based auth.
- **TanStack Query for server state, React Context for auth state** — no Redux, no Zustand. Dashboard is fetch-and-display, not complex client state.
- **Desktop-first responsive** — build full layout first, add responsive overrides via Tailwind breakpoint prefixes (`lg:`, `xl:`).

### CRITICAL: Auth Architecture Gap

The current backend (`POST /auth/login`) returns JWT as a JSON bearer token. The architecture doc specifies dashboard auth should use httpOnly cookies. **This story must add a separate dashboard login endpoint that sets cookies.** The existing Bearer flow must continue to work for API callers.

**Decision:** Add `POST /auth/login/dashboard` alongside the existing `POST /auth/login`. The dashboard endpoint sets httpOnly cookies; the existing endpoint returns bearer tokens. `get_current_org_id()` checks both sources (Bearer header first, cookie second).

### Design System — Key Values

| Property | Value |
|---|---|
| Primary color | Indigo `#4F46E5` (hover: `#4338CA`) |
| Background | White `#FFFFFF` |
| Surface/sidebar | Near-white `#FAFAFA` |
| Border | Zinc `#E4E4E7` |
| Text primary | Near-black `#18181B` |
| Text secondary | Gray `#71717A` |
| UI font | Inter, 14px base |
| Code font | JetBrains Mono |
| Card padding | 24px, 1px border, 4px radius |
| Sidebar width | 240px (full) / 64px (collapsed) |
| Content max-width | 1200px, centered |
| Breakpoints | `<1024px` mobile, `1024-1279px` tablet, `>=1280px` desktop |

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/api/auth.py`** — existing signup/login endpoints. Signup returns fake UUID on duplicate (anti-enumeration). Login uses timing-equalized password comparison.
- **`gateway/services/auth_service.py`** — `create_jwt_token()`, `verify_jwt_token()` using PyJWT with HS256. Add cookie-specific helpers here.
- **`gateway/schemas/auth.py`** — `SignupRequest(email, password)`, `LoginRequest(email, password)`, `SignupResponse`, `LoginResponse`. Extend for cookie auth.
- **`gateway/middleware/auth.py`** — `get_current_org_id()` currently extracts Bearer token via `HTTPBearer`. Must be extended to also check cookies.
- **`gateway/api/api_keys.py`** — existing dashboard API endpoints at `/dashboard/api-keys`. Already protected by `get_current_org_id`. Will work with cookie auth once middleware is updated.
- **`gateway/api/router.py`** — mounts `/auth` and `/dashboard` routers. Add new dashboard login route here.
- **`gateway/main.py`** — CORS middleware already configured with `allowed_origins`. Static file mounting goes here.
- **`gateway/core/config.py`** — JWT settings exist (`jwt_secret_key`, `jwt_expire_minutes`). Add refresh token settings.
- **`tests/conftest.py`** — shared fixtures for real Postgres, Redis, and app client. Reuse for cookie auth tests.

### What NOT to Touch

- Do NOT modify the Bearer token auth flow — API callers depend on it
- Do NOT add Cloudflare Turnstile yet — deferring bot prevention to a later story
- Do NOT implement Overview page content (Story 4.3 owns that)
- Do NOT implement API Keys page content (Story 4.2 owns that)
- Do NOT implement Usage page content (Story 5.2 owns that)
- Do NOT add dark mode polish — enable infrastructure only (CSS variable toggle)
- Do NOT implement email verification — MVP accepts any valid email format
- Do NOT add password reset — deferred to Phase 2 (Story 4.5)
- Do NOT add the OpenAPI client generation script — Story 4.4 owns that

### Responsive Sidebar Implementation

```
>=1280px (xl:)  → Full 240px sidebar with text labels
1024-1279px (lg:) → Collapsed 64px sidebar, icon-only + Tooltip
<1024px (default) → Hidden sidebar, hamburger button + Sheet overlay
```

Use Tailwind classes: `hidden lg:flex` for collapsed sidebar, `hidden xl:flex` for full sidebar. Sheet component from shadcn/ui for mobile drawer.

### Accessibility Checklist

- [ ] Skip link: `<a href="#main" class="sr-only focus:not-sr-only">Skip to main content</a>`
- [ ] Semantic HTML: `<nav>`, `<main id="main">`, `<header>`
- [ ] `aria-label` on icon-only buttons
- [ ] `aria-live` region for form error announcements
- [ ] `aria-describedby` linking inputs to error messages
- [ ] Focus ring visible on keyboard navigation (Radix default)
- [ ] Color contrast: all combinations pass WCAG AA (verified in UX spec)
- [ ] Tab order matches visual order

### Project Structure Notes

New files:
```
dashboard/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js (or CSS-based Tailwind v4 config)
├── index.html
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── globals.css                     # Tailwind + shadcn CSS variables
    ├── lib/utils.ts                    # shadcn cn() utility
    ├── components/
    │   ├── ui/                         # shadcn/ui components (auto-generated)
    │   ├── layout/
    │   │   ├── DashboardLayout.tsx     # Shell: sidebar + content
    │   │   └── Sidebar.tsx             # Navigation sidebar
    │   └── auth/
    │       └── ProtectedRoute.tsx      # Auth guard
    ├── hooks/
    │   └── useAuth.ts                  # Auth context + JWT management
    ├── pages/
    │   ├── Login.tsx
    │   ├── Signup.tsx
    │   ├── Dashboard.tsx               # Placeholder for Story 4.3
    │   ├── ApiKeys.tsx                 # Placeholder for Story 4.2
    │   ├── Usage.tsx                   # Placeholder for Story 5.2
    │   └── Settings.tsx                # Placeholder
    └── types/
        └── index.ts                    # Shared TypeScript types
```

Modified backend files:
- `gateway/api/auth.py` — add `/auth/login/dashboard`, `/auth/refresh`, `/auth/logout`
- `gateway/services/auth_service.py` — add cookie JWT helpers, refresh token logic
- `gateway/middleware/auth.py` — extend `get_current_org_id()` for cookie auth
- `gateway/core/config.py` — add refresh token settings
- `gateway/main.py` — add static file mounting + SPA fallback
- `gateway/api/router.py` — mount new auth routes

New backend files:
- `gateway/models/refresh_token.py` — RefreshToken SQLAlchemy model
- `migrations/versions/xxxx_add_refresh_tokens.py` — Alembic migration

Test files:
- `tests/api/test_auth_cookies.py` — cookie-based auth tests
- `tests/api/test_static_serving.py` — SPA static serving tests
- Dashboard Vitest tests in `dashboard/src/__tests__/`

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
- 476 backend tests currently pass — this story must not break any existing tests

### Previous Story Intelligence (Story 3.4)

- **476 tests pass** — baseline for regression testing
- **Branch naming:** `feat/story-X.Y-description`, merged via PR
- **Code review patterns:** Expect scrutiny on: cookie security attributes (HttpOnly, Secure, SameSite), refresh token storage, CSRF considerations
- **f-string anti-pattern in structlog** — never use f-strings in structlog calls
- **Key patterns established:** structured logging, test fixtures, middleware lifecycle
- **Architecture doc compliance is enforced** — reviewers check against architecture decisions

### Git Intelligence (Recent Commits)

- `1259b14` Merge PR #30: Story 3.4 in-memory quality scoring
- `0315ef5` feat: add in-memory miner quality scoring with EMA and DB persistence (Story 3.4)
- `99ec4c1` Merge PR #29: Story 3.3 security hardening
- `b51dbf4` feat: add security hardening with log redaction, security headers, and TLS config (Story 3.3)
- Pattern: feature branches merged via PR. Branch naming: `feat/story-X.Y-description`. Each story is one commit + merge.

### Security Considerations

- **httpOnly cookies prevent XSS token theft** — JavaScript cannot read the token
- **SameSite=Lax prevents CSRF for GET** — POST requires CSRF mitigation. Since login/logout are POST, consider adding a CSRF token or using `SameSite=Strict`. `Lax` is acceptable for MVP since all state-changing dashboard operations are API calls with JSON content-type (which browsers won't send cross-origin).
- **Secure flag** — cookies sent only over HTTPS. In development (`debug=True`), omit the Secure flag.
- **Refresh token rotation** — each use of a refresh token issues a new one and invalidates the old. Prevents replay attacks.
- **Refresh token in httpOnly cookie** — separate cookie, longer expiry (7 days), same security attributes.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 4, Story 4.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture, Authentication & Security]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Layout Structure, Sidebar, Responsive, Accessibility, Design System]
- [Source: gateway/api/auth.py — existing signup/login endpoints]
- [Source: gateway/services/auth_service.py — JWT creation/verification]
- [Source: gateway/middleware/auth.py — get_current_org_id dependency]
- [Source: gateway/core/config.py — JWT settings, CORS config]
- [Source: gateway/main.py — CORS middleware, static file mounting target]
- [Source: gateway/api/api_keys.py — existing dashboard API key endpoints]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Scaffolded React SPA with Vite 7 + TypeScript + React 19 + Tailwind CSS v4 + shadcn-style UI components (Button, Card, Input, Label, Sheet, Separator, Tooltip, DropdownMenu) + React Router + TanStack Query + Inter/JetBrains Mono fonts. Configured path aliases, Vite dev proxy, and Tailwind theme with Indigo primary color system.
- Task 2: Added cookie-based JWT auth for dashboard. Created RefreshToken model + migration. Added POST /auth/login/dashboard (sets httpOnly cookies), POST /auth/refresh (token rotation), POST /auth/logout (revoke + clear cookies). Updated get_current_org_id to accept both Bearer header and cookie. Added allow_credentials to CORS. Existing Bearer auth unchanged.
- Task 3: Created Login and Signup pages with centered card layout, form validation on submit, field-level error messages with aria-describedby, loading states, and auto-login after signup.
- Task 4: Built responsive dashboard shell — 240px full sidebar (>=1280px), 64px collapsed icon-only (1024-1279px), hidden with Sheet drawer (<1024px). Semantic HTML with skip link, nav, main, header. Navigation groups with active state detection via NavLink.
- Task 5: Implemented AuthProvider using React Context with cookie-based auth. Auth check on mount via protected endpoint probe. ProtectedRoute component redirects to /login if unauthenticated.
- Task 6: Configured React Router with public (/login, /signup) and protected routes (/dashboard, /dashboard/api-keys, /dashboard/usage, /dashboard/settings). Added placeholder pages. Configured FastAPI static file serving for dashboard/dist/ with SPA catch-all fallback.
- Task 7: 11 new backend tests for cookie auth (dashboard login, refresh rotation, logout, cookie-on-dashboard-endpoints, bearer-still-works, hash determinism). 489 total tests pass (up from 478). Ruff clean, mypy clean.

### Change Log

- 2026-03-14: Story 4.1 implementation complete — React SPA with Vite + Tailwind + shadcn-style components, cookie-based JWT auth with refresh token rotation, responsive dashboard shell, static file serving
- 2026-03-14: Code review #1 — 7 issues fixed (3 HIGH, 3 MEDIUM, 1 LOW): implemented actual Login/Signup forms with validation (were stubs), moved inline import to module level, added refresh token cleanup on rotation, improved SPA path traversal check, hardened test fixture assertion, removed Vite boilerplate
- 2026-03-14: Code review #2 — 6 issues fixed (0 HIGH, 4 MEDIUM, 2 LOW): eliminated JWT encode-decode round-trip via login_with_org_id, added GET /auth/me endpoint so email persists after refresh, added expired refresh token test, extracted shared form validation utility, fixed Sidebar prop type, removed empty assets dir

### File List

New frontend files:
- dashboard/vite.config.ts
- dashboard/tsconfig.app.json (updated with path aliases)
- dashboard/src/index.css — Tailwind v4 + theme variables
- dashboard/src/main.tsx — App entry point
- dashboard/src/App.tsx — Router + providers
- dashboard/src/lib/utils.ts — cn() utility
- dashboard/src/types/index.ts — Shared TypeScript types
- dashboard/src/hooks/useAuth.ts — Auth context + cookie-based auth
- dashboard/src/components/ui/button.tsx
- dashboard/src/components/ui/input.tsx
- dashboard/src/components/ui/label.tsx
- dashboard/src/components/ui/card.tsx
- dashboard/src/components/ui/separator.tsx
- dashboard/src/components/ui/tooltip.tsx
- dashboard/src/components/ui/sheet.tsx
- dashboard/src/components/ui/dropdown-menu.tsx
- dashboard/src/components/layout/Sidebar.tsx
- dashboard/src/components/layout/DashboardLayout.tsx
- dashboard/src/components/auth/ProtectedRoute.tsx
- dashboard/src/pages/Login.tsx
- dashboard/src/pages/Signup.tsx
- dashboard/src/pages/Dashboard.tsx (placeholder)
- dashboard/src/pages/ApiKeys.tsx (placeholder)
- dashboard/src/pages/Usage.tsx (placeholder)
- dashboard/src/pages/SettingsPage.tsx (placeholder)

New backend files:
- gateway/models/refresh_token.py — RefreshToken SQLAlchemy model
- migrations/versions/f8828ff1eb3b_add_refresh_tokens_table.py — Alembic migration

Modified backend files:
- gateway/core/config.py — Added refresh_token_expire_days setting
- gateway/models/__init__.py — Added RefreshToken to exports
- gateway/services/auth_service.py — Added create_refresh_token, rotate_refresh_token, revoke_refresh_token
- gateway/api/auth.py — Added /auth/login/dashboard, /auth/refresh, /auth/logout endpoints
- gateway/middleware/auth.py — Updated get_current_org_id for cookie + Bearer auth
- gateway/main.py — Added static file serving, SPA fallback, allow_credentials in CORS

Test files:
- tests/api/test_auth_cookies.py — 11 new tests for cookie-based auth
