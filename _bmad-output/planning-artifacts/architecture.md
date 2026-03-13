---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-03-12'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/prd-validation-report.md
  - _bmad-output/planning-artifacts/product-brief-tao-gateway-2026-03-11.md
  - obsidian-vault/AI/kb/Bittensor/tao-gateway-plan.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/README.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/01-architecture.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/02-yuma-consensus.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/03-subnets.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/04-mining.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/05-validation.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/06-sdk-reference.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/07-synapse-protocol.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/08-tokenomics.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/09-governance.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/10-development-guide.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/11-project-opportunities.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/12-glossary.md
workflowType: 'architecture'
project_name: 'tao-gateway'
user_name: 'Cevin'
date: '2026-03-12'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
46 FRs across 12 capability groups covering developer account management, API key lifecycle, three subnet endpoints (SN1 text, SN19 image, SN62 code), subnet discovery and health, usage monitoring, rate limiting, error handling, miner routing, security, operator administration, data privacy, and adapter extensibility. The requirements are clean (validated at 4.8/5 SMART score) with strong traceability from 7 user journeys.

**Non-Functional Requirements:**
27 NFRs across 6 quality attribute categories. The architecture-driving NFRs are:
- **Performance:** <200ms p95 gateway overhead for text/code, <500ms for image, <10ms key validation, <5ms rate limit check, 50 concurrent requests at MVP
- **Security:** One-way key hashing, TLS 1.2+, wallet encryption at rest, hotkey isolation per subnet, key redaction in all logs, input validation, output sanitization
- **Scalability:** Stateless request handling for horizontal scaling, external state stores, time-partitioned usage records
- **Reliability:** 99.5% uptime target, miner failure isolation, graceful degradation per subnet, cached metagraph fallback
- **Data Retention:** 90-day detailed usage, 48-hour debug content TTL, 30-day rolling miner scores, indefinite aggregated summaries

**Scale & Complexity:**
- Primary domain: API backend with blockchain/web3 integration (Bittensor SDK)
- Complexity level: High
- Estimated architectural components: ~12 major components (API layer, auth middleware, rate limiter, 3 subnet adapters, miner selector, metagraph sync, usage metering, database layer, cache layer, dashboard, health monitoring)

### Technical Constraints & Dependencies

- **Language constraint:** Python (required by Bittensor SDK — wallet, Dendrite, metagraph, Synapse are all Python-native)
- **Bittensor SDK:** Hard dependency for all network interaction. Pin to specific version, test upgrades in staging. SDK uses Pydantic v2 for Synapse models.
- **Async requirement:** Dendrite queries are async. FastAPI's async support aligns well. The gateway must handle concurrent requests to miners without blocking.
- **Chain state dependency:** Metagraph must stay fresh (within 5 minutes) via background sync. Sync takes up to 30 seconds and must not block request handling.
- **Wallet file system:** Bittensor wallets are stored as files (~/.bittensor/wallets/). Coldkey encrypted, hotkeys unencrypted. Gateway needs file system access to wallet directory with strict permissions.
- **Network dependency:** Gateway queries miners via HTTP (Dendrite → Axon). Miner availability is variable — no SLAs, miners can go offline at any time.
- **OpenAI compatibility:** SN1 response schema must pass through `openai.ChatCompletion` client parsing unchanged — hard integration constraint.

### Cross-Cutting Concerns Identified

1. **Authentication:** Every API request must be authenticated via bearer token. Key lookup, hash comparison, and key validation touch every endpoint.
2. **Rate limiting:** Per-key, per-subnet enforcement on every request. Requires atomic cache operations and response header injection.
3. **Structured logging with redaction:** Every component must log without exposing API keys, wallet keys, or sensitive credentials. Requires a logging framework with built-in redaction.
4. **Metagraph state access:** Adapters need metagraph for miner discovery, miner selector needs it for scoring, health endpoints need it for status. Shared state that must be thread-safe and periodically refreshed.
5. **Error classification:** Gateway must distinguish between its own errors (500) and upstream miner failures (502/504). This affects error handling in every adapter and the routing layer.
6. **Usage metering:** Every request must record metadata (key ID, subnet, timestamp, status, latency, tokens) for billing, monitoring, and analytics. Must not add significant latency.
7. **Output sanitization:** Every miner response must be validated/sanitized before returning to the developer. Miners are untrusted — malicious content is possible.
8. **Request metadata headers:** Every response includes gateway-specific headers (miner UID, latency, subnet) for debugging and observability.

## Starter Template Evaluation

### Primary Technology Domain

API backend (Python/FastAPI) with Bittensor SDK integration and embedded React SPA dashboard.

### Starter Options Considered

| Option | Verdict |
|---|---|
| **tiangolo/full-stack-fastapi-template** | Rejected — bundles React + SQLModel + Chakra UI + Docker. Too opinionated for a project with Bittensor SDK as a core dependency. Would require significant removal/rework. |
| **cookiecutter-fastapi** variants | Rejected — most are outdated or assume standard CRUD patterns. None account for blockchain SDK integration or background metagraph sync. |
| **Clean scaffold (custom)** | **Selected** — Purpose-built project structure matching the PRD's component requirements. No template debt. |

### Selected Approach: Clean Scaffold

**Rationale:** The Bittensor SDK integration, subnet adapter pattern, and metagraph sync lifecycle don't map to any existing template. A clean scaffold avoids template debt and lets every structural decision serve the actual architecture.

**Initialization Commands:**

```bash
# Project setup with uv
uv init tao-gateway
cd tao-gateway

# Backend dependencies
uv add fastapi[standard] uvicorn[standard] pydantic[email] pydantic-settings
uv add sqlalchemy[asyncio] asyncpg alembic
uv add redis[hiredis]
uv add bittensor
uv add argon2-cffi python-jose[cryptography]
uv add structlog

# Dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov httpx
uv add --dev ruff mypy pre-commit

# Dashboard (React SPA with Vite)
npm create vite@latest dashboard -- --template react-ts
```

**Language & Runtime:**
- Python 3.12 (stable, broad package support, compatible with Bittensor SDK 10.x)
- TypeScript for dashboard (React SPA)

**Package Management:**
- uv (Rust-based, 10-100x faster than pip/poetry, used by official FastAPI template)

**Database & Migrations:**
- SQLAlchemy 2.x with async engine (asyncpg driver)
- Alembic for schema migrations

**Styling Solution (Dashboard):**
- Tailwind CSS (default with Vite React template)

**Build Tooling:**
- Vite for dashboard SPA build
- Docker Compose for local dev (gateway + postgres + redis)
- FastAPI serves the dashboard's static build in production

**Testing Framework:**
- pytest + pytest-asyncio for async test support
- httpx TestClient for API integration tests
- pytest-cov for coverage

**Code Quality:**
- ruff (linting + formatting, replaces flake8/black/isort)
- mypy for type checking
- pre-commit hooks

**Logging:**
- structlog for structured JSON logging with built-in key redaction

**Development Experience:**
- FastAPI auto-reload via uvicorn
- Vite HMR for dashboard
- Auto-generated OpenAPI docs at /docs

**Note:** Project initialization using these commands should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data modeling: SQLAlchemy 2.x with separate Pydantic schemas
- Auth: JWT in httpOnly cookies (dashboard), bearer token (API)
- API key hashing: argon2
- Subnet adapter pattern: Fat base, thin adapters
- Metagraph sync: Shared in-memory objects, 2-minute background sync
- Error handling: Global exception handler with typed exceptions
- Rate limiting: Custom Redis Lua scripts

**Important Decisions (Shape Architecture):**
- Background tasks: asyncio (FastAPI lifespan), note: evaluate ARQ for Phase 2
- Caching: Layered (in-memory metagraph, Redis key cache, Redis rate limits, in-memory miner scores)
- Dashboard: React SPA (Vite + TanStack Query + Recharts), served by FastAPI
- API client: Generated from OpenAPI spec via openapi-fetch
- Infrastructure: DO Droplet + Managed Postgres + Caddy + GitHub Actions

**Deferred Decisions (Post-MVP):**
- Streaming responses (SSE) — Phase 2
- EMA-based miner quality scoring — Phase 2
- Multi-miner querying (k-of-n) — Phase 2
- Stripe billing integration — Phase 2
- Migration from asyncio background tasks to ARQ — Phase 2 if needed
- Kubernetes / horizontal scaling — Phase 3+

### Data Architecture

| Decision | Choice | Rationale |
|---|---|---|
| ORM | SQLAlchemy 2.x | Mature, proven, clear separation from Pydantic API schemas. Avoids confusion with Bittensor SDK's own Pydantic models. |
| Schemas | Separate Pydantic v2 models | Explicit boundary between DB models and API request/response schemas |
| Migrations | Alembic | Standard for SQLAlchemy, auto-generates migration scripts |
| Metagraph cache | In-memory Python objects | Fastest access (~0ms), refreshed by background task every 2 min |
| API key cache | Redis, 60s TTL | Avoids DB + argon2 verify on every request after first auth |
| Rate limit state | Redis, atomic Lua scripts | Must be external for future multi-instance scaling |
| Miner scores | In-memory, periodic DB flush | Updated on every request, DB write would be wasteful per-request |
| Usage records | Async append to Postgres, monthly partitions | Fire-and-forget after response, daily aggregation via background task |

### Authentication & Security

| Decision | Choice | Rationale |
|---|---|---|
| API authentication | Bearer token (`Authorization: Bearer tao_sk_live_...`) | Industry standard for REST APIs, OpenAI-compatible |
| API key hashing | argon2 (via passlib/pwdlib) | Modern standard, GPU-resistant, Password Hashing Competition winner |
| Dashboard auth | JWT in httpOnly cookies, 15-30 min expiry + refresh tokens | Stateless, aligns with API-first architecture, no server-side session store |
| Wallet storage | SDK default path, coldkey encrypted, hotkeys per subnet, Docker volume mount with 700 permissions | Follows SDK conventions, restricts file access |
| Secrets management | Host environment variables on Droplet, pydantic-settings loads from env vars (priority) then .env (fallback for local dev only) | No secrets in git, no .env files with secrets in production |

### API & Communication Patterns

| Decision | Choice | Rationale |
|---|---|---|
| Error handling | Global exception handler with typed exception hierarchy (`GatewayError` → `MinerTimeoutError`, `MinerInvalidResponseError`, `SubnetUnavailableError`, etc.) | Consistent error responses, clean route handlers |
| Rate limiting | Custom Redis Lua scripts, per-key × per-subnet × three time windows (minute/day/month) | PRD's compound rate limit model is too specific for any library |
| Adapter pattern | Fat base class (miner selection, Dendrite query, response validation, sanitization, usage metering) + thin concrete adapters (~50 lines each: `to_synapse`, `from_response`, config) | Adding a new subnet adapter is straightforward, proving extensibility |
| Metagraph sync | Shared in-memory metagraph per subnet, asyncio background task, 2-min interval, cached fallback on failure, staleness exposed in /v1/health | Fastest access path, within 5-min freshness NFR |
| Background tasks | asyncio tasks in FastAPI lifespan (metagraph sync, score flush, usage aggregation, debug log cleanup) | Simplest for MVP single-instance. Evaluate ARQ in Phase 2 if needed. |

### Frontend Architecture

| Decision | Choice | Rationale |
|---|---|---|
| Framework | React SPA with Vite, served as static files by FastAPI | Single deployment, no separate service, modern DX |
| State management | TanStack Query (server state) + React Context (auth state) | Dashboard is mostly fetch-and-display, no complex client state |
| API client | Generated via openapi-fetch from FastAPI's OpenAPI spec | Fully typed, stays in sync with backend automatically |
| Charting | Recharts | React-native, declarative, good defaults for usage/latency charts |
| Styling | Tailwind CSS | Default with Vite, utility-first, fast to build dashboards |

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|---|---|---|
| Hosting | DigitalOcean Droplet | Full control, Docker Compose, wallet file access, affordable |
| Database | DO Managed Postgres ($15/mo) | Automated backups, point-in-time recovery, no DB admin |
| Cache | Redis in Docker Compose | Cache/rate limiter, not durable state — self-hosted is fine |
| Reverse proxy | Caddy | Auto-TLS (Let's Encrypt), ~5 lines of config |
| CI/CD | GitHub Actions | Free for public repos, test → build → SSH deploy on merge to main |
| Containerization | Docker Compose | Local dev and production, single Droplet |
| Environment config | pydantic-settings, env vars (priority) > .env (local dev fallback) | Secrets as host env vars, never in git |

### Decision Impact Analysis

**Implementation Sequence:**
1. Project scaffold (uv, FastAPI, Docker Compose with Postgres + Redis)
2. Database models + Alembic migrations (API keys, usage records, miner scores)
3. Auth middleware (API key validation, argon2 hashing, Redis cache)
4. Rate limiting middleware (Lua scripts, response headers)
5. Bittensor SDK integration (wallet setup, metagraph sync background task)
6. Base adapter class + SN1 adapter (proves the pattern)
7. SN19 + SN62 adapters
8. Error handling (typed exceptions, global handler)
9. Usage metering (async write, aggregation task)
10. Health + models endpoints
11. Dashboard (React SPA, key management, usage charts)
12. Caddy + deployment pipeline

**Cross-Component Dependencies:**
- Auth middleware depends on: database (key lookup), Redis (key cache)
- Rate limiting depends on: auth (needs key ID), Redis (counters)
- Adapters depend on: metagraph sync (miner discovery), miner selector (routing)
- Usage metering depends on: auth (key ID), adapter response (latency, status, tokens)
- Dashboard depends on: all API endpoints being stable
- Health endpoint depends on: metagraph sync state

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Database Naming:**
- Tables: `snake_case`, plural (`api_keys`, `usage_records`, `miner_scores`)
- Columns: `snake_case` (`created_at`, `api_key_id`, `subnet_id`)
- Foreign keys: `{referenced_table_singular}_id` (`org_id`, `api_key_id`)
- Indexes: `ix_{table}_{columns}` (`ix_usage_records_created_at`)
- Constraints: `uq_{table}_{columns}`, `ck_{table}_{column}`

**API Naming:**
- Endpoints: lowercase, plural nouns, kebab-case for multi-word (`/v1/chat/completions`, `/v1/api-keys`)
- JSON fields in request/response: `snake_case` (matches Python, matches OpenAI convention)
- Custom headers: `X-TaoGateway-{Name}` (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`)
- Query params: `snake_case`

**Python Code Naming:**
- Files/modules: `snake_case` (`miner_selector.py`, `rate_limiter.py`)
- Classes: `PascalCase` (`SubnetAdapter`, `MinerSelector`, `GatewayError`)
- Functions/methods: `snake_case` (`select_miner`, `to_synapse`)
- Constants: `UPPER_SNAKE_CASE` (`DEFAULT_SYNC_INTERVAL`, `MAX_RETRY_COUNT`)

**TypeScript/React (Dashboard) Naming:**
- Components: `PascalCase` files and names (`ApiKeyTable.tsx`, `UsageChart.tsx`)
- Hooks: `camelCase` with `use` prefix (`useApiKeys`, `useUsageStats`)
- Utilities: `camelCase` files (`formatDate.ts`, `apiClient.ts`)
- Types/interfaces: `PascalCase` (`ApiKey`, `UsageRecord`)

### Format Patterns

**API Response — Success:**
No wrapper. Subnet endpoints return the response directly in the format appropriate to that subnet (OpenAI-compatible for SN1, image data for SN19, code for SN62). Gateway metadata goes in headers, not the response body.

**API Response — Error:**
```json
{
  "error": {
    "type": "rate_limit_exceeded",
    "message": "Rate limit exceeded for SN1. Retry after 12 seconds.",
    "code": 429,
    "subnet": "sn1",
    "retry_after": 12
  }
}
```
Consistent error envelope. `type` is machine-readable (`snake_case`), `message` is human-readable.

**Dates:** ISO 8601 strings everywhere (`2026-03-12T14:30:00Z`). Never Unix timestamps in API responses.

**Nulls:** Use `null` in JSON, never omit the field. Explicit nulls prevent ambiguity.

### Structure Patterns

**Test Organization:**
- `tests/` directory at project root (not co-located)
- Mirrors source structure: `tests/api/`, `tests/subnets/`, `tests/core/`
- Test files: `test_{module}.py` (`test_auth.py`, `test_sn1_adapter.py`)
- Fixtures in `tests/conftest.py` (shared) and per-directory `conftest.py`

**Module Organization:**
- By feature/domain, not by type. `subnets/sn1.py` not `adapters/text.py`
- Each module is self-contained with its models, schemas, and logic
- Shared code in `core/` (config, database, redis, bittensor SDK setup)
- Cross-cutting middleware in `middleware/` (auth, rate limit, usage metering)

### Process Patterns

**Logging:**
- Use `structlog` bound loggers (not stdlib `logging`)
- Every log entry includes: `event` (what happened), `subnet` (if applicable), `api_key_prefix` (first 12 chars only, never full key)
- Log levels: `info` for request lifecycle, `warning` for miner failures/sync issues, `error` for gateway failures
- Never log: full API keys, wallet keys, request/response content (unless debug mode)

**Async Patterns:**
- All DB operations via async SQLAlchemy (`async with session`)
- All Redis operations via async redis (`aioredis`)
- Dendrite queries via `await dendrite(...)` (SDK is async-native)
- Background tasks via `asyncio.create_task()` in FastAPI lifespan
- Never use `sync_to_async` wrappers or blocking calls in async handlers

**Import Ordering (enforced by ruff):**
1. Standard library
2. Third-party packages
3. Bittensor SDK
4. Local application modules

**Dependency Injection:**
- Use FastAPI's `Depends()` for request-scoped dependencies (DB session, current user, rate limiter)
- Use app state (`app.state`) for singleton/shared objects (metagraph, miner selector, Dendrite)
- Never use module-level globals for mutable state

### Enforcement Guidelines

**All AI Agents MUST:**
- Follow naming conventions exactly as defined above — no exceptions, no "improvements"
- Use the error response envelope for all error responses
- Use `structlog` for logging, never `print()` or stdlib `logging`
- Use `Depends()` for request-scoped state and `app.state` for singletons
- Write tests in `tests/` mirroring the source structure
- Use async for all I/O operations (DB, Redis, Dendrite, HTTP)

**Pattern Enforcement:**
- ruff enforces import ordering and code style
- mypy enforces type annotations
- Pre-commit hooks run both on every commit
- PR reviews verify naming conventions and structural patterns

## Project Structure & Boundaries

### Complete Project Directory Structure

```
tao-gateway/
├── pyproject.toml                    # uv project config, dependencies
├── uv.lock                           # Locked dependencies
├── alembic.ini                       # Alembic migration config
├── Dockerfile                        # Gateway container
├── docker-compose.yml                # Local dev: gateway + postgres + redis
├── docker-compose.prod.yml           # Production: gateway + redis (managed DB external)
├── Caddyfile                         # Reverse proxy + auto-TLS config
├── .env.example                      # Template for local dev env vars (no secrets)
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── LICENSE                           # MIT
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Test + lint on push/PR
│       └── deploy.yml                # Build + deploy on merge to main
│
├── gateway/                          # Python backend (FastAPI)
│   ├── __init__.py
│   ├── main.py                       # FastAPI app creation, lifespan, static mount
│   │
│   ├── core/                         # Shared infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                 # pydantic-settings: all env var config
│   │   ├── database.py               # Async SQLAlchemy engine, session factory
│   │   ├── redis.py                  # Async Redis connection
│   │   ├── bittensor.py              # SDK init: wallet, subtensor, dendrite
│   │   ├── logging.py                # structlog setup, key redaction processors
│   │   └── exceptions.py             # Exception hierarchy (GatewayError → subtypes)
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── organization.py           # organizations table
│   │   ├── api_key.py                # api_keys table
│   │   ├── usage_record.py           # usage_records table (partitioned)
│   │   └── miner_score.py            # miner_scores table
│   │
│   ├── schemas/                      # Pydantic v2 request/response schemas
│   │   ├── __init__.py
│   │   ├── chat.py                   # OpenAI-compatible chat completion schemas
│   │   ├── images.py                 # Image generation request/response
│   │   ├── code.py                   # Code generation request/response
│   │   ├── models.py                 # /v1/models response schema
│   │   ├── health.py                 # /v1/health response schema
│   │   ├── usage.py                  # /v1/usage response schema
│   │   ├── auth.py                   # Login, signup, token schemas
│   │   ├── api_keys.py              # Key management schemas
│   │   └── errors.py                 # Error response envelope schema
│   │
│   ├── api/                          # Route handlers
│   │   ├── __init__.py
│   │   ├── router.py                 # Root router, mounts all sub-routers
│   │   ├── chat.py                   # POST /v1/chat/completions (SN1)
│   │   ├── images.py                 # POST /v1/images/generate (SN19)
│   │   ├── code.py                   # POST /v1/code/completions (SN62)
│   │   ├── models.py                 # GET /v1/models
│   │   ├── health.py                 # GET /v1/health
│   │   ├── usage.py                  # GET /v1/usage
│   │   ├── auth.py                   # POST /auth/signup, /auth/login, /auth/refresh
│   │   ├── api_keys.py              # CRUD /dashboard/api-keys
│   │   └── admin.py                  # Operator endpoints (FR37-40)
│   │
│   ├── middleware/                    # FastAPI middleware
│   │   ├── __init__.py
│   │   ├── auth.py                   # Bearer token validation, key lookup + cache
│   │   ├── rate_limit.py             # Per-key × per-subnet rate limiting
│   │   ├── usage.py                  # Async usage record write after response
│   │   └── error_handler.py          # Global exception → HTTP response mapping
│   │
│   ├── subnets/                      # Subnet adapter layer
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseAdapter ABC (fat base: query, validate, sanitize)
│   │   ├── sn1_text.py              # SN1 adapter: TextGenSynapse → OpenAI format
│   │   ├── sn19_image.py            # SN19 adapter: ImageGenSynapse → image response
│   │   ├── sn62_code.py             # SN62 adapter: CodeSynapse → code response
│   │   └── registry.py              # Adapter registry: netuid → adapter instance
│   │
│   ├── routing/                      # Miner selection & metagraph
│   │   ├── __init__.py
│   │   ├── selector.py               # MinerSelector: pick best miner by incentive score
│   │   ├── metagraph_sync.py         # Background task: sync metagraph per subnet
│   │   └── scorer.py                 # Miner score tracking (in-memory + DB flush)
│   │
│   ├── services/                     # Business logic services
│   │   ├── __init__.py
│   │   ├── auth_service.py           # Signup, login, JWT creation/validation
│   │   ├── api_key_service.py        # Key generation, hashing, rotation, revocation
│   │   └── usage_service.py          # Usage queries, aggregation, dashboard data
│   │
│   └── tasks/                        # Background tasks (asyncio lifespan)
│       ├── __init__.py
│       ├── metagraph.py              # Metagraph sync loop (2-min interval)
│       ├── score_flush.py            # Persist in-memory miner scores to DB
│       ├── usage_aggregation.py      # Daily usage rollups
│       └── debug_cleanup.py          # Delete debug content logs after 48h
│
├── migrations/                       # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                     # Auto-generated migration scripts
│
├── scripts/                          # Utility scripts
│   ├── rate_limit.lua                # Redis Lua: token bucket rate limiter
│   ├── seed_dev.py                   # Seed dev data (test org, API key)
│   └── generate_api_client.sh        # Regenerate TypeScript client from OpenAPI spec
│
├── dashboard/                        # React SPA (Vite + TypeScript)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx                  # App entry point
│       ├── App.tsx                   # Root component, router setup
│       ├── api/                      # Generated OpenAPI client
│       │   └── client.ts             # openapi-fetch generated client
│       ├── components/
│       │   ├── layout/               # Shell, sidebar, header
│       │   ├── auth/                 # LoginForm, SignupForm
│       │   ├── api-keys/             # ApiKeyTable, CreateKeyModal, KeyRow
│       │   ├── usage/                # UsageChart, SubnetBreakdown, LatencyChart
│       │   └── common/               # Button, Card, Input, LoadingSpinner
│       ├── hooks/
│       │   ├── useAuth.ts            # Auth context + JWT management
│       │   ├── useApiKeys.ts         # TanStack Query: key CRUD
│       │   └── useUsage.ts           # TanStack Query: usage data
│       ├── pages/
│       │   ├── Login.tsx
│       │   ├── Signup.tsx
│       │   ├── Dashboard.tsx         # Account overview
│       │   ├── ApiKeys.tsx           # Key management
│       │   └── Usage.tsx             # Usage monitoring
│       ├── types/
│       │   └── index.ts              # Shared TypeScript types
│       └── utils/
│           └── formatDate.ts
│
└── tests/                            # All tests (mirrors gateway/ structure)
    ├── conftest.py                   # Shared fixtures: test DB, Redis, app client
    ├── api/
    │   ├── test_chat.py              # SN1 endpoint tests
    │   ├── test_images.py            # SN19 endpoint tests
    │   ├── test_code.py              # SN62 endpoint tests
    │   ├── test_models.py
    │   ├── test_health.py
    │   ├── test_auth.py
    │   └── test_api_keys.py
    ├── middleware/
    │   ├── test_auth_middleware.py
    │   ├── test_rate_limit.py
    │   └── test_error_handler.py
    ├── subnets/
    │   ├── test_base_adapter.py
    │   ├── test_sn1.py
    │   ├── test_sn19.py
    │   └── test_sn62.py
    ├── routing/
    │   ├── test_selector.py
    │   └── test_metagraph_sync.py
    ├── services/
    │   ├── test_auth_service.py
    │   ├── test_api_key_service.py
    │   └── test_usage_service.py
    └── integration/
        ├── test_full_request_flow.py  # End-to-end: auth → rate limit → adapter → response
        └── test_metagraph_lifecycle.py # Sync startup, failure, recovery
```

### Architectural Boundaries

**API Boundaries:**
- `/v1/*` — Public API endpoints. Require bearer token auth. Rate limited.
- `/auth/*` — Authentication endpoints (signup, login, refresh). No bearer token required.
- `/dashboard/*` — Dashboard API endpoints. Require JWT cookie auth.
- `/admin/*` — Operator endpoints. Require admin-level auth.
- `/docs` — Auto-generated OpenAPI docs. Public.

**Service Boundaries:**
- `gateway/api/` calls `gateway/services/` — never accesses DB directly
- `gateway/services/` calls `gateway/models/` for DB access
- `gateway/api/` (subnet routes) calls `gateway/subnets/` adapters
- `gateway/subnets/` calls `gateway/routing/` for miner selection
- `gateway/middleware/` operates independently, injected via FastAPI middleware chain

**Data Boundaries:**
- SQLAlchemy models are the only code that touches the database
- Pydantic schemas are the only code that defines API request/response shapes
- No SQLAlchemy model is ever returned directly in an API response
- Redis access is encapsulated in `core/redis.py` and `middleware/rate_limit.py`

### Requirements to Structure Mapping

| FR Group | Primary Location | Supporting Files |
|---|---|---|
| FR1-3 (Account Management) | `api/auth.py`, `services/auth_service.py` | `models/organization.py`, `schemas/auth.py` |
| FR4-7 (API Key Management) | `api/api_keys.py`, `services/api_key_service.py` | `models/api_key.py`, `schemas/api_keys.py` |
| FR8-9 (SN1 Text Gen) | `api/chat.py`, `subnets/sn1_text.py` | `schemas/chat.py` |
| FR10-11 (SN19 Image Gen) | `api/images.py`, `subnets/sn19_image.py` | `schemas/images.py` |
| FR12-13 (SN62 Code Gen) | `api/code.py`, `subnets/sn62_code.py` | `schemas/code.py` |
| FR14-16 (Discovery/Health) | `api/models.py`, `api/health.py` | `schemas/models.py`, `schemas/health.py` |
| FR17-20 (Usage Monitoring) | `api/usage.py`, `services/usage_service.py` | `models/usage_record.py`, `schemas/usage.py` |
| FR21-23 (Rate Limiting) | `middleware/rate_limit.py` | `scripts/rate_limit.lua` |
| FR24-27 (Error Handling) | `middleware/error_handler.py`, `core/exceptions.py` | `schemas/errors.py` |
| FR28-30 (Miner Routing) | `routing/selector.py`, `routing/metagraph_sync.py` | `routing/scorer.py` |
| FR31-36 (Security) | `middleware/auth.py`, `core/logging.py` | `core/bittensor.py` (wallet) |
| FR37-40 (Operator Admin) | `api/admin.py` | `services/usage_service.py` |
| FR41-43 (Data Privacy) | `middleware/usage.py`, `tasks/debug_cleanup.py` | `core/logging.py` |
| FR44 (API Docs) | `main.py` (FastAPI auto-generates) | — |
| FR45-46 (Extensibility) | `subnets/base.py`, `subnets/registry.py` | — |

### Data Flow

```
Request → Caddy (TLS) → FastAPI
  → error_handler middleware (wraps everything)
  → auth middleware (validate key, cache lookup)
  → rate_limit middleware (Lua script check)
  → route handler
    → adapter.to_synapse(request)
    → selector.select_miner(metagraph)
    → dendrite.query(axon, synapse)
    → adapter.from_response(synapse)
    → sanitize output
  → usage middleware (async write after response)
  → response + gateway headers
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All technology choices are compatible and version-aligned. SQLAlchemy 2.x + asyncpg + Alembic is proven. FastAPI + Pydantic v2 aligns with Bittensor SDK's Pydantic v2 Synapse models. Redis (hiredis) for caching/rate limiting alongside managed Postgres for persistence is standard. React SPA served by FastAPI eliminates CORS complexity. No version conflicts or contradictory decisions found.

**Pattern Consistency:**
Naming conventions are internally consistent across all domains (snake_case Python/JSON, PascalCase React/types). The fat-base/thin-adapter pattern aligns with FastAPI's Depends() injection model. Error response envelope is uniform. Logging patterns (structlog with redaction) apply consistently across all components.

**Structure Alignment:**
Project structure directly supports every architectural decision. Subnet adapters have a dedicated layer (`subnets/`), cross-cutting concerns are middleware-based (`middleware/`), metagraph and routing are isolated (`routing/`), and background tasks are explicit (`tasks/`). Service boundaries prevent layer-skipping: API → services → models.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**
All 46 FRs are mapped to specific files and directories in the project structure. Every FR group has a primary location and supporting files identified. The adapter registry pattern (FR45-46) ensures new subnet support follows the same pattern.

**Non-Functional Requirements Coverage:**
- **Performance:** In-memory metagraph (~0ms), Redis key cache (60s TTL), Lua rate limit scripts (<5ms), async usage writes (non-blocking)
- **Security:** argon2 key hashing, JWT httpOnly cookies, TLS via Caddy, wallet file permissions, structlog key redaction, output sanitization in base adapter
- **Scalability:** Stateless request handling, external state stores, time-partitioned usage records
- **Reliability:** Cached metagraph fallback on sync failure, miner failure isolation per adapter, staleness exposed in /v1/health
- **Data Retention:** debug_cleanup.py (48h), monthly usage partitions (90-day detailed), rolling miner scores (30-day)

### Implementation Readiness Validation ✅

**Decision Completeness:**
All critical decisions are documented with specific technologies and versions. Implementation patterns include concrete examples (error response format, logging rules, async patterns). Enforcement mechanisms are defined (ruff, mypy, pre-commit).

**Structure Completeness:**
Every file and directory is named with a purpose annotation. Integration points (middleware chain order, adapter registry, shared metagraph state via app.state) are explicitly defined. Test structure mirrors source structure.

**Pattern Completeness:**
All potential conflict points are addressed: import ordering, dependency injection strategy, async-only I/O rules, naming conventions across Python and TypeScript, and clear data boundary rules (no ORM models in API responses).

### Gap Analysis Results

**Critical Gaps:** None found.

**Important Gaps (non-blocking, address during implementation):**
1. **Dependency correction:** Initialization commands list `passlib[bcrypt]` but architecture specifies argon2. Correct dependency: `argon2-cffi` (or `pwdlib[argon2]`).
2. **Debug content storage:** The 48h debug cleanup task exists but storage location for request/response debug content is not explicit. Recommend a `debug_logs` Postgres table with TTL enforcement.
3. **CORS configuration:** Not mentioned. SPA is same-origin (served by FastAPI), so not needed for dashboard. Public API callers are expected to be server-side, so CORS is not required for MVP. Document this assumption.

**Nice-to-Have Gaps:**
1. Database connection pool sizing not specified (asyncpg defaults are suitable for MVP scale)
2. Redis health not included in /v1/health response (metagraph staleness is covered)
3. Dashboard SPA routing strategy not specified (recommend browser history mode with FastAPI catch-all fallback)

### Validation Issues Addressed

1. **argon2 dependency** — Will be corrected during project initialization story. The architectural decision (argon2) is correct; only the example install command needs updating.
2. **Debug content storage** — This is an implementation detail that will be resolved when implementing FR41-43. The cleanup task is architecturally placed correctly.
3. **CORS** — Confirmed not needed for MVP. Same-origin SPA and server-side API consumers mean no CORS headers required.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**✅ Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — all critical decisions are made, no blocking gaps, patterns are comprehensive enough for consistent AI agent implementation.

**Key Strengths:**
- Clean separation between Bittensor SDK integration and HTTP API concerns
- Fat-base/thin-adapter pattern makes subnet expansion straightforward (~50 lines per new adapter)
- Layered caching strategy matches each access pattern's characteristics
- Cross-cutting concerns handled via middleware chain with clear ordering
- Complete FR-to-file mapping eliminates ambiguity during implementation
- Technology choices are mature, well-documented, and compatible

**Areas for Future Enhancement:**
- Streaming responses (SSE) for SN1 text generation — Phase 2
- EMA-based miner scoring with quality tracking — Phase 2
- ARQ task queue if background tasks outgrow asyncio — Phase 2
- Multi-miner querying (k-of-n redundancy) — Phase 2
- Stripe billing integration — Phase 2
- Horizontal scaling (multiple gateway instances) — Phase 3+

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions
- When in doubt about a naming, format, or pattern decision, this document is authoritative

**First Implementation Priority:**
Project scaffold: `uv init`, install dependencies (correcting argon2-cffi), create directory structure, Docker Compose (gateway + postgres + redis), Alembic init, basic FastAPI app with health endpoint.
