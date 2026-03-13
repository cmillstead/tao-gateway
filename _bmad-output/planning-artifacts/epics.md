---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# tao-gateway - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for tao-gateway, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Developer Account Management**
- FR1: Developer can create an account with email and password
- FR2: Developer can log in and access their dashboard
- FR3: Developer can view their account overview and current tier status

**API Key Management**
- FR4: Developer can generate new API keys with environment-identifying prefixes
- FR5: Developer can view active API keys (masked, showing only prefix)
- FR6: Developer can rotate an API key (generate new, invalidate old)
- FR7: Developer can revoke an API key immediately

**Subnet Access — Text Generation (SN1)**
- FR8: Developer can send text generation requests via OpenAI-compatible chat completions endpoint
- FR9: Developer can receive responses that work with existing OpenAI client libraries unchanged
- FR47: System supports streaming responses (SSE) for SN1 chat completions, compatible with OpenAI client stream=True

**Subnet Access — Image Generation (SN19)**
- FR10: Developer can send image generation requests with prompt text, resolution, and style parameters
- FR11: Developer can receive generated image data as base64-encoded PNG or image URL in the response

**Subnet Access — Code Generation (SN62)**
- FR12: Developer can send code generation requests with prompt, target programming language, and optional context
- FR13: Developer can receive generated code as a string with language identifier in the response

**Subnet Discovery & Health**
- FR14: Developer can list all available subnets and their capabilities
- FR15: Developer can check health status of each subnet
- FR16: Developer can view per-subnet availability percentage and p50/p95 response time metrics

**Usage Monitoring**
- FR17: Developer can view their request counts per subnet over time
- FR18: Developer can view p50, p95, and p99 latency metrics per subnet
- FR19: Developer can view their remaining free tier quota per subnet
- FR20: Developer can view their usage history with daily granularity for the last 90 days

**Rate Limiting**
- FR21: System enforces per-subnet, per-key request rate limits
- FR22: System returns rate limit status in response headers on every request
- FR23: System returns actionable error with retry timing when rate limit is exceeded

**Error Handling & Debugging**
- FR24: System returns distinct error codes for gateway errors vs. upstream miner failures
- FR25: System includes miner identifier and latency metadata in response headers
- FR26: System returns field-level validation errors for malformed requests
- FR27: Developer can enable per-key debug mode for temporary request/response content logging

**Miner Routing**
- FR28: System selects miners based on metagraph incentive scores
- FR29: System maintains metagraph state within 5 minutes of current via background synchronization
- FR30: System detects and avoids routing to offline or unresponsive miners

**Security**
- FR31: System authenticates all API requests via bearer token
- FR32: System stores API keys using industry-standard one-way hashing (never plaintext)
- FR33: System redacts API keys from all log output
- FR34: System validates all request input against defined schemas
- FR35: System sanitizes miner response content before returning to developer
- FR36: System enforces TLS on all API endpoints

**Operator Administration**
- FR37: Operator can view request volume, error rates, and latency across all subnets
- FR38: Operator can view metagraph sync status and freshness
- FR39: Operator can view new signups, weekly active developers, and requests per developer
- FR40: Operator can view miner response quality scores

**Data Privacy**
- FR41: System logs request metadata only (no content) by default
- FR42: System auto-deletes debug mode content logs after 48 hours
- FR43: System computes quality scores in-memory without persisting request/response content

**API Documentation**
- FR44: Developer can access auto-generated OpenAPI documentation with interactive request testing

**Extensibility**
- FR45: Operator can add support for a new subnet without modifying core gateway code
- FR46: System supports subnet-specific request/response schemas through a consistent translation interface

**Resource Management**
- FR48: System cancels upstream miner queries when the client disconnects mid-request

### NonFunctional Requirements

**Performance**
- NFR1: <200ms p95 gateway overhead for text (SN1) and code (SN62) endpoints
- NFR2: <500ms p95 gateway overhead for SN19 image generation
- NFR3: <10ms API key validation per request (hash comparison cached via token lookup)
- NFR4: <5ms rate limit check per request (atomic cache operation)
- NFR5: Metagraph sync completes within 30 seconds, does not block request handling
- NFR6: <2 seconds dashboard page load (server response + DOMContentLoaded)
- NFR7: Support 50 concurrent requests per gateway instance at MVP

**Security**
- NFR8: API keys cryptographically hashed (one-way), never stored or logged in plaintext
- NFR9: Coldkey encrypted at rest, hotkeys isolated per subnet, neither exposed via API or logs
- NFR10: TLS 1.2+ required on all endpoints, no plaintext HTTP
- NFR11: All request payloads validated against defined input schemas before processing
- NFR12: All miner responses validated against expected schema before returning to developer
- NFR13: API keys, wallet keys, and sensitive credentials redacted from all log output and error responses
- NFR14: Pin all dependencies, monitor for known vulnerabilities

**Scalability**
- NFR15: Single instance supports 100 active developers averaging 50 requests/day (5,000 requests/day total)
- NFR16: Stateless request handling (no session affinity) for horizontal scaling without architectural changes
- NFR17: Database schema designed for partitioning by time if usage records grow large
- NFR18: Rate limiting via distributed cache, separated from application state, scales independently

**Reliability**
- NFR19: 99.5% gateway uptime target (best effort, ~3.6 hours downtime/month acceptable)
- NFR20: Individual miner timeouts do not cascade to gateway-wide failures
- NFR21: If metagraph sync fails, gateway continues on cached state with staleness indicator in health endpoint
- NFR22: Usage records and API keys backed by persistent storage with daily backups and point-in-time recovery
- NFR23: If all miners unavailable for a subnet, return 503 with clear message; other subnets unaffected

**Integration**
- NFR24: Bittensor SDK pinned to specific version, upgrades tested in staging before production
- NFR25: Gateway handles metagraph API unavailability gracefully (cached fallback)
- NFR26: SN1 responses must pass through openai.ChatCompletion client parsing unchanged — hard integration constraint

**Data Retention**
- NFR27: Usage records 90-day detailed retention, indefinite aggregated; debug content 48h TTL; miner scores 30-day rolling window

### Additional Requirements

**From Architecture:**
- Starter template: Clean scaffold (no template), project initialization via `uv init` + custom directory structure — impacts Epic 1 Story 1
- Language/runtime: Python 3.12, TypeScript for dashboard (React SPA)
- Package management: uv (Rust-based)
- ORM: SQLAlchemy 2.x with async engine (asyncpg), separate Pydantic v2 schemas
- Auth strategy: JWT in httpOnly cookies (dashboard), bearer token (API); argon2 for key hashing (dependency: argon2-cffi, not passlib[bcrypt])
- Adapter pattern: Fat base class + thin concrete adapters (~50 lines each)
- Metagraph sync: Shared in-memory objects, 2-minute background sync interval
- Error handling: Global exception handler with typed exception hierarchy (GatewayError → subtypes)
- Rate limiting: Custom Redis Lua scripts, per-key x per-subnet x three time windows
- Background tasks: asyncio tasks in FastAPI lifespan (metagraph sync, score flush, usage aggregation, debug cleanup)
- Dashboard: React SPA (Vite + TanStack Query + Recharts + shadcn/ui + Tailwind), served as static files by FastAPI
- API client: Generated from OpenAPI spec via openapi-fetch
- Infrastructure: DO Droplet + Managed Postgres ($15/mo) + Redis in Docker + Caddy (auto-TLS) + GitHub Actions CI/CD
- Logging: structlog with built-in key redaction processors
- Code quality: ruff (lint+format), mypy (types), pre-commit hooks
- Implementation sequence: Scaffold → DB models → Auth middleware → Rate limiting → Bittensor SDK → Base adapter + SN1 → SN19 + SN62 → Error handling → Usage metering → Health/models → Dashboard → Deployment

**From UX Design:**
- Desktop-first responsive: Full sidebar >=1280px, collapsed sidebar 1024-1279px, hidden sidebar <1024px
- Accessibility: WCAG 2.1 AA target; semantic HTML, skip link, aria-labels on icon buttons, aria-live for clipboard feedback, color never sole indicator
- Component library: shadcn/ui (Radix primitives) for keyboard navigation, focus management, ARIA support
- Quickstart experience: After key creation, inline quickstart with developer's actual API key pre-filled in curl/Python snippets
- Subnet-as-capability framing: Display "Text Generation," "Image Generation," "Code Generation" — not SN1/SN19/SN62
- Key creation UX: One-click generate, key shown once with copy-to-clipboard, no configuration wizard
- Key rotation UX: Single flow combining generate-new + revoke-old
- Usage at a glance: Dashboard landing shows quota consumption per subnet as progress bars/counters
- Professional design language: No emoji, no mascots, no playful copy; Stripe/OpenAI/Vercel-inspired
- Color palette: Zinc neutrals, Indigo-600 primary, Emerald/Amber/Red status colors
- Error UX: Every error answers: what happened, why, what to do next
- Touch targets: Minimum 44x44px on mobile breakpoints
- No animations at MVP: If added later, respect prefers-reduced-motion

**Known Gaps (Post-MVP):**
- SN19 async/webhook pattern: End-to-end image generation may take 10-30s. Consider async job pattern (return job ID, poll or webhook for completion) in Phase 2.
- Multi-key subnet scoping: Restrict API keys to specific subnets or endpoints for security. Phase 2 candidate per PRD phasing.
- Typed SDK/client libraries: Python/TypeScript client generated from OpenAPI spec would accelerate TaoAgent integration. Phase 2 candidate.
- Email verification: Signup has no email verification (intentional — reduces onboarding friction for time-to-first-request). Must be added as a Phase 2 prerequisite before enabling Stripe paid tiers, to prevent abuse.
- CORS on /v1/* endpoints: Not needed for MVP (SPA is same-origin, API consumers are server-side). Consider adding CORS headers on public API endpoints post-MVP if browser-based developer tools (Postman web, etc.) need direct access.
- Cloudflare Turnstile: UX spec references Turnstile for bot prevention on signup. Not in architecture or epics. Add as Phase 2 hardening if signup abuse becomes an issue.
- Product brief vs PRD projection reconciliation: The product brief projects $15K MRR at 12 months (optimistic). The PRD recalibrates to $500-1K/mo profit at 12 months (conservative solo-operator economics). The PRD numbers are authoritative for implementation decisions. The brief's projections represent a best-case scaling scenario, not the MVP validation target.

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 1 | Account creation (API-level) |
| FR2 | Epic 4 | Dashboard login access |
| FR3 | Epic 4 | Account overview and tier status |
| FR4 | Epic 1 | API key generation (API-level) |
| FR5 | Epic 4 | View active keys (masked) in dashboard |
| FR6 | Epic 4 | Key rotation via dashboard |
| FR7 | Epic 4 | Key revocation via dashboard |
| FR8 | Epic 1 | Text generation via chat completions endpoint |
| FR9 | Epic 1 | OpenAI-compatible responses |
| FR10 | Epic 2 | Image generation requests |
| FR11 | Epic 2 | Image response (base64/URL) |
| FR12 | Epic 2 | Code generation requests |
| FR13 | Epic 2 | Code response with language ID |
| FR14 | Epic 2 | List available subnets |
| FR15 | Epic 2 | Subnet health status |
| FR16 | Epic 2 | Per-subnet availability and latency metrics |
| FR17 | Epic 5 | Request counts per subnet |
| FR18 | Epic 5 | Latency metrics per subnet |
| FR19 | Epic 5 | Remaining free tier quota |
| FR20 | Epic 5 | 90-day usage history |
| FR21 | Epic 3 | Per-subnet, per-key rate limits |
| FR22 | Epic 3 | Rate limit headers on every response |
| FR23 | Epic 3 | Actionable rate limit error with retry timing |
| FR24 | Epic 3 | Distinct gateway vs. miner error codes |
| FR25 | Epic 3 | Miner ID and latency in response headers |
| FR26 | Epic 3 | Field-level validation errors |
| FR27 | Epic 5 | Per-key debug mode |
| FR28 | Epic 1 | Miner selection by incentive score |
| FR29 | Epic 1 | Metagraph sync within 5 minutes |
| FR30 | Epic 1 | Detect and avoid offline miners |
| FR31 | Epic 1 | Bearer token authentication |
| FR32 | Epic 1 | One-way key hashing |
| FR33 | Epic 3 | Key redaction in logs |
| FR34 | Epic 1 | Input schema validation |
| FR35 | Epic 1 | Output sanitization of miner responses |
| FR36 | Epic 3 | TLS enforcement |
| FR37 | Epic 6 | Operator: request volume, error rates, latency |
| FR38 | Epic 6 | Operator: metagraph sync status |
| FR39 | Epic 6 | Operator: signup and activity metrics |
| FR40 | Epic 6 | Operator: miner quality scores |
| FR41 | Epic 3 | Metadata-only logging by default |
| FR42 | Epic 5 | Debug content auto-delete after 48h |
| FR43 | Epic 3 | In-memory quality scoring (no content persisted) |
| FR44 | Epic 1 | Auto-generated OpenAPI docs |
| FR45 | Epic 2 | Add subnet without modifying core code |
| FR46 | Epic 2 | Consistent translation interface |
| FR47 | Epic 1 | Streaming responses (SSE) for SN1 |
| FR48 | Epic 1 | Cancel upstream on client disconnect |

## Epics and Stories

## Epic 1: Gateway Foundation & Text Generation

Developer authenticates with an API key and makes text generation requests (including streaming) to SN1 via an OpenAI-compatible endpoint. Keys created via API/CLI. Auto-generated API docs available at /docs.

### Story 1.1: Project Scaffold & Health Endpoint

As a **developer/operator**,
I want a deployable gateway skeleton with health check and interactive API docs,
So that I can verify the infrastructure is running and explore available endpoints.

**Acceptance Criteria:**

**Given** a fresh clone of the repository
**When** I run `docker compose up`
**Then** the gateway, PostgreSQL, and Redis containers start successfully
**And** the gateway is accessible on the configured port

**Given** the gateway is running
**When** I send `GET /v1/health`
**Then** I receive a 200 response with JSON indicating gateway status
**And** the response includes service version

**Given** the gateway is running
**When** I navigate to `/docs`
**Then** I see auto-generated OpenAPI documentation with interactive testing (Swagger UI)
**And** `/redoc` also serves documentation

**Given** the project root
**When** I run `uv run ruff check` and `uv run mypy gateway`
**Then** both pass with zero errors on the scaffold code

**Given** the project structure
**When** I inspect the directory layout
**Then** it matches the Architecture document's defined structure (gateway/, tests/, migrations/, scripts/, dashboard/)
**And** structlog is configured with JSON output and key redaction processors
**And** Alembic is initialized and connected to the async database engine

### Story 1.2: Developer Account & API Key Creation

As a **developer**,
I want to create an account and generate an API key via the API,
So that I can authenticate my requests to the gateway.

**Acceptance Criteria:**

**Given** I am a new user
**When** I send `POST /auth/signup` with email and password
**Then** I receive a 201 response with account confirmation
**And** the password is never stored in plaintext

**Given** I have an account
**When** I send `POST /auth/login` with valid credentials
**Then** I receive a JWT token for subsequent authenticated requests

**Given** I am authenticated
**When** I send `POST /dashboard/api-keys` to generate a new key
**Then** I receive the full API key exactly once (prefixed `tao_sk_live_` or `tao_sk_test_`)
**And** the key is stored as an argon2 hash in PostgreSQL (never plaintext)
**And** only the key prefix is stored in plaintext for identification

**Given** I have an API key
**When** I send a request with `Authorization: Bearer tao_sk_live_...`
**Then** the auth middleware validates the key via Redis cache (cache hit) or DB lookup + argon2 verify (cache miss)
**And** the validated key ID is available to downstream handlers via FastAPI Depends()

**Given** I send a request with an invalid or missing API key
**When** the auth middleware processes the request
**Then** I receive a 401 response with the standard error envelope
**And** the invalid key is not logged (redacted)

**Given** the Redis key cache
**When** a key is validated against the database
**Then** the result is cached in Redis with a 60-second TTL
**And** subsequent requests within the TTL skip the DB + argon2 verification (NFR3: <10ms)

### Story 1.3: Bittensor Integration & Miner Selection

As a **developer**,
I want the gateway to connect to the Bittensor network and select quality miners,
So that my requests are routed to responsive, high-quality miners.

**Acceptance Criteria:**

**Given** the gateway starts up
**When** the FastAPI lifespan initializes
**Then** the Bittensor wallet (coldkey + SN1 hotkey) is loaded from the configured path
**And** the Dendrite client is initialized and stored in `app.state`
**And** the metagraph for SN1 is synced and stored in `app.state`

**Given** the gateway is running
**When** the metagraph background sync task fires (every 2 minutes)
**Then** the metagraph is refreshed from the network within 30 seconds (NFR5)
**And** request handling is not blocked during sync
**And** the sync timestamp is recorded for staleness tracking

**Given** the metagraph sync fails
**When** the network is unreachable or times out
**Then** the gateway continues operating on the cached metagraph state (NFR21, NFR25)
**And** a warning is logged with structured metadata
**And** the `/v1/health` endpoint reports metagraph staleness

**Given** a request needs miner selection for SN1
**When** the MinerSelector is called
**Then** it returns the top miner by incentive score from the current metagraph
**And** miners with zero incentive or known-offline status are excluded (FR30)

**Given** wallet files on disk
**When** the gateway accesses them
**Then** the coldkey is encrypted at rest (NFR9)
**And** hotkeys are isolated per subnet
**And** neither coldkey nor hotkey content appears in any log output

### Story 1.4: SN1 Text Generation Endpoint

As a **developer**,
I want to send text generation requests to an OpenAI-compatible endpoint,
So that I can use decentralized AI by swapping `base_url` in my existing OpenAI client code.

**Acceptance Criteria:**

**Given** I am authenticated with a valid API key
**When** I send `POST /v1/chat/completions` with an OpenAI-compatible request body (model, messages array)
**Then** the gateway translates my request into a TextGenSynapse
**And** routes it to a selected miner via Dendrite
**And** returns an OpenAI ChatCompletion-formatted JSON response

**Given** the SN1 adapter processes a miner response
**When** the response is returned
**Then** it passes through `openai.ChatCompletion` client parsing unchanged (NFR26)
**And** response headers include `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`

**Given** I send a malformed request body
**When** Pydantic validation fails
**Then** I receive a 422 response with field-level validation errors (FR26)
**And** the error follows the standard error envelope format

**Given** a miner returns an invalid or potentially malicious response
**When** the adapter processes the response
**Then** the output is sanitized against the expected schema before returning to me (FR35, NFR12)

**Given** the selected miner times out
**When** the Dendrite query exceeds the timeout threshold
**Then** I receive a 504 response with the miner UID in the error metadata
**And** the error distinguishes this as an upstream failure, not a gateway error (FR24)

**Given** all SN1 miners are unavailable
**When** the miner selector finds no eligible miners
**Then** I receive a 503 response with a clear message about subnet unavailability (NFR23)
**And** other subnet endpoints remain unaffected

**Given** the base adapter class
**When** a new subnet adapter is needed in the future
**Then** the fat-base/thin-adapter pattern is established: base handles miner selection, Dendrite query, response validation, sanitization; concrete adapter provides `to_synapse()`, `from_response()`, and config (~50 lines)

**Given** normal request handling
**When** measuring gateway-added latency (excluding miner response time)
**Then** p95 overhead is under 200ms (NFR1)

### Story 1.5: Streaming Responses & Request Cancellation

As a **developer**,
I want to stream text generation responses via SSE,
So that I can use `stream=True` with OpenAI client libraries and get tokens as they're generated.

**Acceptance Criteria:**

**Given** I am authenticated with a valid API key
**When** I send `POST /v1/chat/completions` with `stream: true`
**Then** the gateway returns a `text/event-stream` response
**And** tokens are sent as SSE events in OpenAI-compatible `data: {...}` format
**And** the stream ends with `data: [DONE]`

**Given** I am streaming a response using the OpenAI Python client
**When** I iterate over `client.chat.completions.create(stream=True)`
**Then** the response parses correctly through the OpenAI client library without modification

**Given** I am receiving a streaming response
**When** I disconnect (close the connection) mid-stream
**Then** the gateway detects the disconnection
**And** cancels the upstream Dendrite query to the miner (FR48)
**And** resources are released promptly

**Given** a streaming request
**When** the miner times out or returns an error mid-stream
**Then** the gateway sends an SSE error event with miner UID and error details
**And** closes the stream cleanly

**Given** a streaming response
**When** response headers are sent
**Then** they include `X-TaoGateway-Miner-UID` and `X-TaoGateway-Subnet`
**And** `X-TaoGateway-Latency-Ms` reflects time-to-first-token

## Epic 2: Multi-Subnet Expansion

Developer accesses image generation (SN19) and code generation (SN62) through the same API key. Can discover all available subnets via /v1/models and check their health via /v1/health. Validates the adapter pattern generalizes beyond SN1.

### Story 2.1: SN19 Image Generation Endpoint

As a **developer**,
I want to send image generation requests and receive generated images,
So that I can add AI image capabilities to my application through the same API key I use for text generation.

**Acceptance Criteria:**

**Given** I am authenticated with a valid API key
**When** I send `POST /v1/images/generate` with prompt text, resolution, and style parameters
**Then** the gateway translates my request into an ImageGenSynapse
**And** routes it to a selected SN19 miner via Dendrite
**And** returns generated image data as base64-encoded PNG or image URL in the response

**Given** the gateway starts up
**When** the FastAPI lifespan initializes
**Then** the metagraph for SN19 is synced alongside SN1
**And** the SN19 hotkey is loaded from the configured wallet path
**And** the metagraph background sync task covers both SN1 and SN19

**Given** a miner returns an invalid image response
**When** the SN19 adapter processes the response
**Then** the output is validated against the expected image schema before returning
**And** invalid responses result in a 502 error with miner UID in metadata

**Given** all SN19 miners are unavailable
**When** the miner selector finds no eligible miners for SN19
**Then** I receive a 503 with a clear message about SN19 unavailability
**And** SN1 endpoints remain fully functional (NFR23)

**Given** normal image generation request handling
**When** measuring gateway-added overhead (excluding miner generation time)
**Then** p95 overhead is under 500ms (NFR2)

**Given** the SN19 endpoint
**When** a developer sends an image generation request
**Then** the endpoint timeout is set generously (60-90 seconds) to accommodate miner-side generation time (typically 10-30 seconds)
**And** API documentation clearly states expected response times for image generation vs. text/code endpoints

### Story 2.2: SN62 Code Generation Endpoint

As a **developer**,
I want to send code generation requests and receive generated code,
So that I can integrate AI code generation into my tools through the same gateway.

**Acceptance Criteria:**

**Given** I am authenticated with a valid API key
**When** I send `POST /v1/code/completions` with prompt, target programming language, and optional context
**Then** the gateway translates my request into a CodeSynapse
**And** routes it to a selected SN62 miner via Dendrite
**And** returns generated code as a string with language identifier in the response

**Given** the gateway starts up
**When** the FastAPI lifespan initializes
**Then** the metagraph for SN62 is synced alongside SN1 and SN19
**And** the SN62 hotkey is loaded from the configured wallet path

**Given** a miner returns an invalid code response
**When** the SN62 adapter processes the response
**Then** the output is validated and sanitized against the expected schema
**And** invalid responses result in a 502 error with miner UID in metadata

**Given** all SN62 miners are unavailable
**When** the miner selector finds no eligible miners for SN62
**Then** I receive a 503 with a clear message about SN62 unavailability
**And** SN1 and SN19 endpoints remain fully functional (NFR23)

**Given** normal code generation request handling
**When** measuring gateway-added overhead (excluding miner response time)
**Then** p95 overhead is under 200ms (NFR1)

### Story 2.3: Subnet Discovery & Health

As a **developer**,
I want to discover available subnets and check their health status,
So that I can understand what capabilities are available and route my traffic accordingly.

**Acceptance Criteria:**

**Given** the gateway is running with all adapters registered
**When** I send `GET /v1/models`
**Then** I receive a list of all available subnets with their capabilities
**And** each entry includes: capability name (e.g., "Text Generation"), subnet ID, supported parameters, and current status

**Given** I send `GET /v1/models`
**When** one subnet's miners are all offline
**Then** that subnet still appears in the list but with a status indicating unavailability
**And** available subnets show as healthy

**Given** the gateway is running
**When** I send `GET /v1/health`
**Then** I receive per-subnet health status including availability percentage and p50/p95 response time metrics (FR16)
**And** metagraph sync freshness per subnet is included
**And** overall gateway status is reported

**Given** the metagraph for one subnet is stale
**When** I check `/v1/health`
**Then** that subnet shows a staleness warning with last sync timestamp
**And** other subnets show their current sync status independently

### Story 2.4: Adapter Registry & Extensibility

As an **operator**,
I want to add support for new subnets by registering a thin adapter class,
So that expanding gateway coverage doesn't require modifying core gateway code.

**Acceptance Criteria:**

**Given** the adapter registry module (`subnets/registry.py`)
**When** a new subnet adapter is created following the base adapter pattern
**Then** it can be registered by netuid → adapter instance mapping
**And** the gateway automatically includes it in `/v1/models` and `/v1/health`
**And** no changes to core gateway code (routing, auth, middleware) are required (FR45)

**Given** the base adapter class (`subnets/base.py`)
**When** implementing a new subnet adapter
**Then** the concrete adapter only needs to implement `to_synapse()`, `from_response()`, and configuration
**And** miner selection, Dendrite query, response validation, sanitization, and usage metering are handled by the base class (FR46)
**And** the concrete adapter is approximately 50 lines of code

**Given** the three existing adapters (SN1, SN19, SN62)
**When** I review their implementations
**Then** each follows the same structural pattern via the base class
**And** subnet-specific logic is isolated to the thin adapter layer
**And** shared behavior is not duplicated across adapters

## Epic 3: Rate Limiting & API Hardening

System enforces fair usage with per-key, per-subnet rate limits. Distinct error codes for gateway vs. miner failures. Response metadata headers. Log redaction, TLS, and metadata-only logging.

### Story 3.1: Rate Limiting Engine

As a **developer**,
I want the gateway to enforce fair usage limits and tell me my remaining quota,
So that I can plan my request patterns and handle rate limits gracefully.

**Acceptance Criteria:**

**Given** I am authenticated with a valid API key
**When** I send any request to a subnet endpoint
**Then** the rate limiter checks three time windows: per-minute, per-day, per-month
**And** each window is scoped per-key and per-subnet independently
**And** the check completes in under 5ms (NFR4)

**Given** I am within my rate limits
**When** I receive a response (any status code)
**Then** response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` for the most restrictive active window (FR22)

**Given** I exceed the per-minute rate limit on SN1
**When** my next request arrives
**Then** I receive a 429 response with `Retry-After` header indicating seconds until the window resets
**And** the error body follows the standard error envelope with `type: "rate_limit_exceeded"`, subnet, and retry timing (FR23)
**And** my SN19 and SN62 limits are unaffected

**Given** I exceed the daily limit on SN19
**When** I send another SN19 request
**Then** I receive a 429 with `Retry-After` reflecting the daily window reset
**And** SN1 and SN62 requests still succeed if within their limits

**Given** the rate limiter uses Redis
**When** multiple concurrent requests arrive for the same key
**Then** the Lua script executes atomically — no race conditions on counter updates (NFR18)
**And** rate limit state is external to the application (supports future horizontal scaling)

**Given** the free tier rate limits
**When** a free-tier developer checks their limits
**Then** SN1 allows 10 req/min, 100/day, 1,000/month
**And** SN19 allows 5/min, 50/day, 500/month
**And** SN62 allows 10/min, 100/day, 1,000/month

### Story 3.2: Error Handling & Response Metadata

As a **developer**,
I want clear, distinct error codes and debugging metadata in every response,
So that I can distinguish gateway issues from miner issues and troubleshoot effectively.

**Acceptance Criteria:**

**Given** a gateway-internal error occurs (e.g., database failure, configuration error)
**When** the global exception handler catches it
**Then** I receive a 500 response with `type: "internal_error"` in the error envelope
**And** the error is distinguishable from upstream miner failures (FR24)

**Given** a miner returns an invalid response
**When** the adapter detects the invalid response
**Then** I receive a 502 response with `type: "bad_gateway"` and the miner UID in the error body

**Given** a miner times out
**When** the Dendrite query exceeds the timeout threshold
**Then** I receive a 504 response with `type: "gateway_timeout"` and the miner UID in the error body
**And** the error is distinct from a gateway-side timeout (FR24)

**Given** any successful response from a subnet endpoint
**When** the response is returned
**Then** headers include `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, and `X-TaoGateway-Subnet` (FR25)

**Given** I send a malformed request body
**When** Pydantic validation fails
**Then** I receive a 422 response with field-level errors listing each invalid field, the constraint violated, and the value received (FR26)
**And** the error follows the standard error envelope format

**Given** the typed exception hierarchy
**When** any exception is raised in the gateway
**Then** it maps to a specific HTTP status code and error type via the global exception handler
**And** `GatewayError` subtypes include `MinerTimeoutError`, `MinerInvalidResponseError`, `SubnetUnavailableError`, `RateLimitExceededError`, `AuthenticationError`

### Story 3.3: Security Hardening

As an **operator**,
I want all API keys redacted from logs, TLS enforced on all endpoints, and no request content logged by default,
So that the gateway meets production security standards.

**Acceptance Criteria:**

**Given** any log entry produced by the gateway
**When** an API key value appears in the log context
**Then** structlog redaction processors replace it with a masked value (e.g., `tao_sk_live_****`) (FR33)
**And** wallet keys and other sensitive credentials are also redacted (NFR13)

**Given** the structlog configuration
**When** I review all log output paths (request lifecycle, errors, background tasks)
**Then** no full API key, wallet key, or credential appears in any log level
**And** only the key prefix (first 12 chars) is used for identification in logs

**Given** the production deployment
**When** a client connects to the gateway
**Then** Caddy enforces TLS 1.2+ on all endpoints (FR36, NFR10)
**And** plaintext HTTP requests are redirected to HTTPS
**And** the Caddyfile is configured with auto-TLS via Let's Encrypt

**Given** the default logging policy
**When** a request is processed
**Then** only metadata is logged: timestamp, API key prefix, subnet, endpoint, miner UID, latency, status code, token count (FR41)
**And** request body and response body content are never logged unless debug mode is enabled for that key

### Story 3.4: In-Memory Quality Scoring

As an **operator**,
I want miner quality tracked without persisting request/response content,
So that routing decisions improve over time while respecting data privacy.

**Acceptance Criteria:**

**Given** a successful miner response
**When** the gateway processes the response
**Then** a numeric quality score is computed in-memory based on response validity, latency, and completeness (FR43)
**And** no request or response content is persisted for scoring purposes

**Given** the in-memory miner scores
**When** the score flush background task fires
**Then** only numeric scores and metadata (miner UID, subnet, timestamp) are written to the `miner_scores` table
**And** scores are maintained as a rolling 30-day window (NFR27)

**Given** sampled responses for quality scoring
**When** a response is sampled (~5-10% of requests)
**Then** the content is evaluated in-memory and immediately discarded after scoring
**And** only the resulting numeric score persists

**Given** the miner scores in the database
**When** the MinerSelector routes a request
**Then** it can incorporate historical quality scores alongside metagraph incentive scores for better routing decisions

## Epic 4: Developer Dashboard & Self-Service

Developer signs up, logs in, manages API keys (view, rotate, revoke), sees account overview and quickstart — all through a polished web dashboard. React SPA with JWT httpOnly cookie auth, shadcn/ui components, Tailwind styling. Desktop-first responsive. WCAG 2.1 AA accessibility.

### Story 4.1: Dashboard Shell & Authentication

As a **developer**,
I want to sign up and log in to a polished web dashboard,
So that I can manage my TaoGateway account through a familiar, professional interface.

**Acceptance Criteria:**

**Given** I am a new user
**When** I navigate to the dashboard signup page
**Then** I see a minimal signup form (email, password)
**And** on successful submission, my account is created and I am logged in automatically

**Given** I have an account
**When** I submit the login form with valid credentials
**Then** a JWT is set as an httpOnly cookie (15-30 min expiry) with a refresh token
**And** I am redirected to the dashboard overview page (FR2)

**Given** I am logged in
**When** I view the dashboard on a desktop (>=1280px)
**Then** I see a full 240px left sidebar with grouped navigation (Overview, API Keys, Usage, Settings)
**And** the layout follows Stripe/OpenAI-inspired professional design language

**Given** I am on a small desktop or tablet landscape (1024-1279px)
**When** I view the dashboard
**Then** the sidebar collapses to 64px icon-only mode with hover tooltips
**And** main content expands to fill available width

**Given** I am on a tablet portrait or mobile (<1024px)
**When** I view the dashboard
**Then** the sidebar is hidden, accessible via a hamburger menu (Sheet component)
**And** touch targets are minimum 44x44px

**Given** the dashboard HTML structure
**When** I inspect the page
**Then** it uses semantic elements (`<nav>`, `<main>`, `<header>`)
**And** a skip link is present (hidden, visible on focus, jumps to main content)
**And** all interactive components support keyboard navigation via Radix primitives

**Given** my JWT expires
**When** I make a dashboard request
**Then** the refresh token silently obtains a new JWT
**And** I am not redirected to login unless the refresh token is also expired

### Story 4.2: API Key Management

As a **developer**,
I want to create, view, rotate, and revoke API keys through the dashboard,
So that I can manage my API access without using CLI tools.

**Acceptance Criteria:**

**Given** I am logged in and on the API Keys page
**When** I view my keys
**Then** I see an OpenAI-style table showing each key's prefix (masked), creation date, last used date, and status (FR5)
**And** full key values are never displayed after initial creation

**Given** I click the "Create Key" button
**When** the key is generated
**Then** it appears once in a modal with a prominent copy-to-clipboard button
**And** the key is prefixed `tao_sk_live_` or `tao_sk_test_` based on environment
**And** no configuration wizard or form fields are required — one click to generate
**And** an `aria-live` region announces "Key copied" on clipboard copy

**Given** I want to rotate a key
**When** I select "Rotate" on an existing key
**Then** a single flow generates a new key and revokes the old one atomically (FR6)
**And** the new key is displayed once with copy-to-clipboard
**And** the old key is immediately invalidated

**Given** I want to revoke a key
**When** I select "Revoke" and confirm
**Then** the key is immediately invalidated (FR7)
**And** the key row updates to show revoked status
**And** requests using the revoked key receive 401 immediately

**Given** the API Keys page
**When** I interact using only keyboard
**Then** all actions (create, copy, rotate, revoke) are accessible via keyboard navigation
**And** focus management follows WCAG 2.1 AA guidelines
**And** icon-only buttons have `aria-label` attributes

### Story 4.3: Account Overview & Quickstart

As a **developer**,
I want to see my account status and a quickstart guide with my API key pre-filled,
So that I can understand my tier, see available capabilities, and make my first API call quickly.

**Acceptance Criteria:**

**Given** I am logged in and on the Overview page
**When** the page loads
**Then** I see my account overview including current tier status (free/paid) (FR3)
**And** available capabilities displayed as "Text Generation," "Image Generation," "Code Generation" — not SN1/SN19/SN62
**And** each capability shows a health status indicator (green/yellow/red with text label — color is never the sole indicator)

**Given** I have created at least one API key
**When** I view the quickstart panel
**Then** I see working code snippets (curl and Python tabs) with my actual API key pre-filled
**And** each snippet has a copy-to-clipboard button
**And** the Python example shows an OpenAI client `base_url` swap pattern

**Given** I have not created any API keys yet
**When** I view the Overview page
**Then** the quickstart panel prompts me to create a key first
**And** a direct link/button navigates to the API Keys page

**Given** the Overview page
**When** I check quota consumption
**Then** I see per-subnet quota usage as progress bars or counters (e.g., "847 / 1,000 requests used")
**And** the information is answerable at a glance without clicking

**Given** the page loads
**When** measuring performance
**Then** the page loads in under 2 seconds (NFR6)

### Story 4.4: API Client Generation & Dashboard Build Pipeline

As a **developer**,
I want the dashboard to use a typed API client generated from the backend's OpenAPI spec,
So that the frontend stays in sync with the backend automatically.

**Acceptance Criteria:**

**Given** the FastAPI backend's OpenAPI spec
**When** I run the client generation script (`scripts/generate_api_client.sh`)
**Then** a fully typed TypeScript client is generated via openapi-fetch into `dashboard/src/api/client.ts`
**And** the generated types match all backend request/response schemas

**Given** the dashboard is built (`npm run build` in `dashboard/`)
**When** the FastAPI application starts
**Then** it serves the dashboard's static files (HTML, JS, CSS) from a mounted directory
**And** client-side routing works via a catch-all fallback to `index.html`

**Given** the dashboard SPA
**When** I navigate between pages
**Then** TanStack Query manages server state (API keys, usage data, account info)
**And** React Context manages auth state (JWT, current user)

**Given** the build pipeline
**When** the OpenAPI spec changes (new endpoints, modified schemas)
**Then** regenerating the client reflects the changes with type errors surfacing any frontend incompatibilities
**And** no manual type synchronization is needed

### Story 4.5: Password Reset Flow (DEFERRED — Phase 2)

_Deferred to Phase 2. Requires email sending infrastructure (not in architecture). At MVP scale, manual password resets via operator are acceptable._

## Epic 5: Usage Monitoring & Analytics

Developer monitors request counts, latency metrics (p50/p95/p99), and quota consumption per subnet through the dashboard. 90-day usage history with daily granularity. Debug mode available for troubleshooting with 48h auto-cleanup.

### Story 5.1: Usage Metering & Storage

As a **developer**,
I want my request activity recorded and queryable,
So that I can understand my usage patterns and access historical data via the API.

**Acceptance Criteria:**

**Given** I send any request to a subnet endpoint
**When** the response is returned (any status code)
**Then** the usage middleware asynchronously writes a usage record with: API key ID, subnet, endpoint, miner UID, latency, status code, token count, and timestamp
**And** the write does not add latency to the response (fire-and-forget)
**And** no request or response content is included in the record (FR41 — metadata only)

**Given** usage records accumulate over time
**When** the database stores them
**Then** the `usage_records` table is partitioned by month (NFR17)
**And** detailed records are retained for 90 days
**And** the schema supports efficient queries by key ID, subnet, and time range

**Given** the daily aggregation background task fires
**When** it processes the previous day's detailed records
**Then** it generates daily summaries per key, per subnet (request count, p50/p95/p99 latency, error count, token totals)
**And** aggregated summaries are retained indefinitely (NFR27)

**Given** I am authenticated with a valid API key
**When** I send `GET /v1/usage`
**Then** I receive my request counts per subnet over time (FR17)
**And** p50, p95, and p99 latency metrics per subnet (FR18)
**And** usage history with daily granularity for the last 90 days (FR20)
**And** I can filter by subnet and date range via query parameters

### Story 5.2: Usage Dashboard & Quota Display

As a **developer**,
I want to see my usage and quota status visually in the dashboard,
So that I can monitor my consumption at a glance and know when I'm approaching limits.

**Acceptance Criteria:**

**Given** I am logged in and on the Usage page
**When** the page loads
**Then** I see request count charts per subnet over time (Recharts line/bar charts)
**And** latency metrics displayed as p50, p95, p99 per subnet
**And** I can select date ranges within the last 90 days

**Given** I am on the Usage page
**When** I view quota consumption
**Then** I see my remaining free tier quota per subnet as progress bars or counters (FR19)
**And** each shows explicit numbers (e.g., "847 / 1,000 monthly requests") — not vague indicators
**And** per-minute and per-day limits are also visible

**Given** I am near my quota limit (>80% consumed)
**When** I view the quota display
**Then** the progress bar visually indicates proximity to the limit (amber color + text label)
**And** color is never the sole indicator — text label always accompanies status

**Given** the Usage page charts
**When** I interact with them
**Then** I can toggle between subnets to compare usage patterns
**And** hovering on data points shows exact values
**And** the charts are keyboard-accessible

**Given** the dashboard Overview page (from Epic 4)
**When** I check quota at a glance
**Then** the overview also shows a summary of quota consumption per subnet
**And** links to the full Usage page for detailed drill-down

### Story 5.3: Debug Mode & Content Cleanup

As a **developer**,
I want to temporarily enable debug logging for my API key,
So that I can troubleshoot issues by reviewing my recent request and response content.

**Acceptance Criteria:**

**Given** I am logged in to the dashboard
**When** I enable debug mode for a specific API key
**Then** subsequent requests using that key store request and response content alongside the metadata record (FR27)
**And** debug mode is scoped to the individual key — other keys are unaffected

**Given** debug mode is enabled for my key
**When** I send a request
**Then** the request body and response body are stored in a `debug_logs` table with the usage record reference
**And** a 48-hour TTL is set on each debug entry

**Given** the debug cleanup background task fires
**When** it scans the `debug_logs` table
**Then** all entries older than 48 hours are permanently deleted (FR42)
**And** the deletion is logged as a structured event (count of records purged)

**Given** debug mode is enabled
**When** I view my recent requests in the dashboard (or via API)
**Then** I can see the full request and response content for debug-enabled requests
**And** entries older than 48h are no longer available

**Given** the privacy policy
**When** debug content is stored
**Then** content is never associated with user identity for analytics
**And** content is never used for quality scoring (scoring remains in-memory per FR43)

## Epic 6: Operator Administration

Operator monitors gateway health across all subnets: request volumes, error rates, miner quality scores, metagraph sync status, developer signup and activity metrics. Admin-level auth with separate operator views.

### Story 6.1: Admin API Endpoints

As an **operator**,
I want API endpoints that expose system-wide metrics and health data,
So that I can monitor gateway operations and respond to issues.

**Acceptance Criteria:**

**Given** I am authenticated with admin-level credentials
**When** I send `GET /admin/metrics`
**Then** I receive request volume, error rates, and average latency across all subnets (FR37)
**And** data is broken down per subnet with configurable time range (last hour, 24h, 7d, 30d)

**Given** I am authenticated as admin
**When** I send `GET /admin/metagraph`
**Then** I receive metagraph sync status for each subnet (FR38)
**And** each entry includes: last sync timestamp, staleness duration, sync success/failure status, number of active miners

**Given** I am authenticated as admin
**When** I send `GET /admin/developers`
**Then** I receive signup metrics: total registered developers, new signups (daily/weekly), weekly active developers (FR39)
**And** a per-developer summary showing request counts by subnet and last active timestamp

**Given** I am authenticated as admin
**When** I send `GET /admin/miners`
**Then** I receive miner quality scores per subnet (FR40)
**And** each entry includes: miner UID, incentive score, gateway quality score, response count, average latency, error rate

**Given** the admin auth model
**When** determining if a user is an admin
**Then** admin status is determined by an `is_admin` boolean on the organization record
**And** this flag is set directly in the database (no self-service admin promotion)
**And** Cevin's account is seeded as admin during initial setup

**Given** I am not authenticated or authenticated as a regular developer
**When** I attempt to access any `/admin/*` endpoint
**Then** I receive a 401 or 403 response
**And** admin endpoints are not discoverable in the public OpenAPI docs

### Story 6.2: Operator Dashboard Views

As an **operator**,
I want a dedicated admin section in the dashboard,
So that I can visually monitor system health without querying API endpoints directly.

**Acceptance Criteria:**

**Given** I am logged in as an admin user
**When** I navigate to the admin section
**Then** I see a system health overview with per-subnet cards showing: request volume, error rate, p50/p95 latency, and miner availability
**And** each card uses status indicators (green/amber/red with text labels — color never sole indicator)

**Given** the admin dashboard
**When** I view metagraph status
**Then** I see sync freshness per subnet with last sync timestamp and staleness duration
**And** stale metagraphs (>5 minutes) are visually flagged with a warning indicator

**Given** the admin dashboard
**When** I view developer activity
**Then** I see a table of developers with: signup date, last active, total requests, per-subnet breakdown
**And** summary metrics at the top: total developers, new signups this week, weekly active count

**Given** the admin dashboard
**When** I view miner quality
**Then** I see a per-subnet table of miners sorted by quality score
**And** each row shows: miner UID, incentive score, gateway quality score, request count, average latency, error rate
**And** miners with high error rates or zero recent requests are visually flagged

**Given** I am a regular developer (not admin)
**When** I use the dashboard
**Then** the admin section is not visible in the sidebar navigation
**And** direct navigation to admin routes redirects to the overview page

### Story 6.3: Production Deployment Pipeline

As an **operator**,
I want a CI/CD pipeline and production deployment configuration,
So that code changes are automatically tested and deployed to the live gateway.

**Acceptance Criteria:**

**Given** a push to any branch or a pull request
**When** the GitHub Actions CI workflow runs
**Then** it executes: ruff check, mypy, pytest with coverage
**And** the dashboard builds successfully (`npm run build`)
**And** the workflow fails fast on any check failure

**Given** a merge to the `main` branch
**When** the GitHub Actions deploy workflow runs
**Then** it builds the Docker image, pushes to registry, and deploys to the DigitalOcean Droplet via SSH
**And** the deployment uses `docker-compose.prod.yml` (gateway + Redis, managed Postgres external)

**Given** the production Droplet
**When** the Caddy reverse proxy is configured
**Then** it auto-provisions TLS via Let's Encrypt for the gateway domain
**And** proxies HTTPS traffic to the FastAPI container
**And** the Caddyfile is version-controlled with approximately 5 lines of config

**Given** the production environment
**When** the gateway starts
**Then** it loads secrets from host environment variables (not .env files)
**And** the wallet directory is mounted as a Docker volume with 700 permissions
**And** structlog outputs JSON for log aggregation

**Given** the deployment pipeline
**When** a deployment completes
**Then** the `/v1/health` endpoint confirms the new version is running
**And** zero-downtime deployment is achieved via container restart with health check
