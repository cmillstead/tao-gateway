# Story 3.1: Rate Limiting Engine

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the gateway to enforce fair usage limits and tell me my remaining quota,
So that I can plan my request patterns and handle rate limits gracefully.

## Acceptance Criteria

1. **Given** I am authenticated with a valid API key
   **When** I send any request to a subnet endpoint
   **Then** the rate limiter checks three time windows: per-minute, per-day, per-month
   **And** each window is scoped per-key and per-subnet independently
   **And** the check completes in under 5ms (NFR4)

2. **Given** I am within my rate limits
   **When** I receive a response (any status code)
   **Then** response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` for the most restrictive active window (FR22)

3. **Given** I exceed the per-minute rate limit on SN1
   **When** my next request arrives
   **Then** I receive a 429 response with `Retry-After` header indicating seconds until the window resets
   **And** the error body follows the standard error envelope with `type: "rate_limit_exceeded"`, subnet, and retry timing (FR23)
   **And** my SN19 and SN62 limits are unaffected

4. **Given** I exceed the daily limit on SN19
   **When** I send another SN19 request
   **Then** I receive a 429 with `Retry-After` reflecting the daily window reset
   **And** SN1 and SN62 requests still succeed if within their limits

5. **Given** the rate limiter uses Redis
   **When** multiple concurrent requests arrive for the same key
   **Then** the Lua script executes atomically — no race conditions on counter updates (NFR18)
   **And** rate limit state is external to the application (supports future horizontal scaling)

6. **Given** the free tier rate limits
   **When** a free-tier developer checks their limits
   **Then** SN1 allows 10 req/min, 100/day, 1,000/month
   **And** SN19 allows 5/min, 50/day, 500/month
   **And** SN62 allows 10/min, 100/day, 1,000/month

## Tasks / Subtasks

- [x] Task 1: Create Redis Lua rate limiting script (AC: #1, #5)
  - [x] 1.1 Write `scripts/rate_limit.lua` — atomic token bucket with three time windows (minute/day/month)
  - [x] 1.2 Script accepts: key_id, subnet_id, limits (per-minute, per-day, per-month), current timestamp
  - [x] 1.3 Script returns: allowed (bool), remaining counts per window, reset times per window, most restrictive window info
  - [x] 1.4 Use Redis MULTI/EXEC or single Lua script for atomicity — no race conditions on concurrent increment

- [x] Task 2: Create rate limit middleware (AC: #1, #2, #3, #4, #6)
  - [x] 2.1 Create `gateway/middleware/rate_limit.py` with `Depends()` callable
  - [x] 2.2 Load Lua script on startup, cache script SHA via `register_script` for EVALSHA calls
  - [x] 2.3 Extract `api_key_id` and `subnet_id` from request context (depends on auth middleware running first)
  - [x] 2.4 Look up rate limits for the key's tier and subnet from config
  - [x] 2.5 Call Lua script via registered script with appropriate keys and args
  - [x] 2.6 If allowed: inject `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers into response
  - [x] 2.7 If denied: raise `RateLimitExceededError` with subnet, retry_after, and window info

- [x] Task 3: Define rate limit configuration (AC: #6)
  - [x] 3.1 Add rate limit settings to `gateway/middleware/rate_limit.py` (free tier defaults per subnet)
  - [x] 3.2 Structure: `_SUBNET_RATE_LIMITS = {netuid: {minute: N, day: N, month: N}}`
  - [x] 3.3 Make extensible via `get_subnet_rate_limits()` function for future paid tier support

- [x] Task 4: Integrate into request flow (AC: #1, #2, #3, #4)
  - [x] 4.1 Add rate limit dependency to subnet endpoint routes (after auth, before handler)
  - [x] 4.2 Ensure rate limit headers appear on ALL responses (success, error, streaming)
  - [x] 4.3 Ensure `RateLimitExceededError` is handled by existing `error_handler.py` → 429 response with standard envelope

- [x] Task 5: Write tests (AC: all)
  - [x] 5.1 Create `tests/middleware/test_rate_limit.py` — use real Redis (not mocked)
  - [x] 5.2 Test per-minute window: requests within limit succeed, exceed returns 429
  - [x] 5.3 Test per-day window: daily limit enforcement with correct Retry-After
  - [x] 5.4 Test per-month window: monthly limit enforcement
  - [x] 5.5 Test per-subnet independence: hitting SN1 limit doesn't affect SN19
  - [x] 5.6 Test response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` present on all responses
  - [x] 5.7 Test concurrent requests: verify atomic counter updates (no race conditions)
  - [x] 5.8 Test 429 error body: correct `type`, `subnet`, `retry_after` fields
  - [x] 5.9 Test Redis unavailability: graceful degradation (allow requests or fail-open per design decision)
  - [x] 5.10 Integration test: full flow auth → rate limit → handler → response with headers

## Dev Notes

### Architecture Patterns and Constraints

- **Middleware position:** Rate limit check runs AFTER auth middleware (needs `api_key_id`) and BEFORE route handler. See data flow: `Request -> Caddy -> FastAPI -> error_handler -> auth -> rate_limit -> route handler`
- **Redis Lua scripts:** Architecture mandates custom Lua scripts (not a library) because the compound rate limit model (per-key × per-subnet × three windows) is too specific for generic rate limiting libraries
- **Performance:** Rate limit check MUST complete in <5ms (NFR4). Use `EVALSHA` (not `EVAL`) to avoid re-sending script text on every call
- **Atomicity:** All counter operations within a single Lua script execution — Redis guarantees atomic execution of Lua scripts (NFR18)
- **State externalization:** Rate limit state lives entirely in Redis, not in application memory — this enables future horizontal scaling
- **Dependency injection:** Use FastAPI `Depends()` pattern (consistent with auth middleware), NOT traditional ASGI middleware
- **Error hierarchy:** `RateLimitExceededError` already exists in `gateway/core/exceptions.py` — it's a `GatewayError` subtype mapping to 429

### Rate Limit Configuration (Free Tier)

| Subnet | Per-Minute | Per-Day | Per-Month |
|--------|-----------|---------|-----------|
| SN1    | 10        | 100     | 1,000     |
| SN19   | 5         | 50      | 500       |
| SN62   | 10        | 100     | 1,000     |

### Redis Key Design

- Key pattern: `rate:{api_key_id}:{subnet_id}:{window}` (e.g., `rate:42:sn1:minute`)
- Three keys per API key per subnet: `:minute`, `:day`, `:month`
- TTL per key matches window duration (60s, 86400s, ~2.6M seconds)
- Keys auto-expire — no cleanup needed

### Response Headers

On every response (success or error):
- `X-RateLimit-Limit: {limit}` — max requests for the most restrictive active window
- `X-RateLimit-Remaining: {remaining}` — remaining requests in that window
- `X-RateLimit-Reset: {unix_timestamp}` — when the window resets

On 429 responses additionally:
- `Retry-After: {seconds}` — seconds until the most restrictive window resets

### Error Response Format (429)

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

### Design Decision: Redis Unavailability

When Redis is down, the rate limiter should **fail open** (allow requests) — consistent with existing auth middleware's Redis fallback pattern. Log a warning via structlog. The existing `try_get_redis()` circuit breaker in `gateway/core/redis.py` handles this.

### Existing Code to Leverage

- `gateway/core/redis.py` — Singleton Redis client with circuit breaker, `try_get_redis()` for best-effort access
- `gateway/core/exceptions.py` — `RateLimitExceededError` already defined (GatewayError subtype → 429)
- `gateway/middleware/error_handler.py` — Already maps `GatewayError` subtypes to JSON responses
- `gateway/middleware/auth.py` — Pattern to follow for `Depends()` integration; provides `api_key_id` in request state
- `gateway/core/config.py` — Pydantic `BaseSettings` for env var config
- `tests/conftest.py` — Already cleans `chat_rate:*`, `images_rate:*`, `code_rate:*` Redis keys; add `rate:*` pattern

### Project Structure Notes

- New files: `gateway/middleware/rate_limit.py`, `scripts/rate_limit.lua`, `tests/middleware/test_rate_limit.py`
- Modified files: `gateway/core/config.py` (add rate limit settings), `gateway/api/chat.py` (add rate limit dependency), `gateway/subnets/base.py` or route files (inject rate limit check), `tests/conftest.py` (add `rate:*` cleanup pattern)
- File structure follows existing conventions: middleware in `gateway/middleware/`, tests mirror source tree

### Testing Standards

- **Real Redis required** — hit actual Redis via Docker test container, never mock Redis operations
- **Mock only Bittensor SDK** — everything else uses real infrastructure
- Run: `uv run pytest --tb=short -q`
- Lint: `uv run ruff check gateway/ tests/`
- Types: `uv run mypy gateway/`
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests
- Follow parametrized test pattern from `test_adapter_pattern.py` for multi-subnet scenarios

### Previous Story Intelligence (Story 2.4)

- **Fat Base / Thin Adapter pattern** is load-bearing — `BaseAdapter.execute()` handles the full request lifecycle. Rate limiting should integrate at the dependency/middleware level, not inside adapters
- **Config-driven registration** via `ADAPTER_DEFINITIONS` in `gateway/subnets/__init__.py` — rate limit config per subnet should follow a similar pattern
- `app.state` singletons set during lifespan — consider loading Lua script SHA during lifespan startup
- Test cleanup in `conftest.py` already handles Redis key patterns — extend for rate limit keys
- 387 tests currently pass — this story should not break any existing tests

### Git Intelligence (Recent Commits)

- Recent work completed all of Epic 2 (Stories 2.1-2.4)
- Code follows consistent patterns: structlog logging, Depends() injection, Pydantic schemas, real Redis in tests
- Security scan fixes applied (PR #22): attack surface hardening, data flow fixes — maintain these standards

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#Rate Limiting, Cross-Cutting Concerns, Data Flow]
- [Source: _bmad-output/planning-artifacts/prd.md#FR21-FR23, NFR4, NFR18, API Rate Limiting]
- [Source: gateway/core/exceptions.py — RateLimitExceededError definition]
- [Source: gateway/core/redis.py — Redis client with circuit breaker]
- [Source: gateway/middleware/auth.py — Depends() pattern reference]
- [Source: gateway/middleware/error_handler.py — GatewayError → JSON mapping]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed — comprehensive developer guide created
- Code review completed (2026-03-14): 3 HIGH, 3 MEDIUM, 2 LOW issues found — all fixed
- H1 Fixed: Auth 429 regression — changed subnet default to None
- H2 Fixed: Lua script no longer inflates counters on denied requests (check-before-increment)
- H3 Fixed: Rate limit headers now appear on error responses via request.state
- M1 Fixed: Consolidated duplicate rate limit helpers into shared `enforce_rate_limit()`
- M2 Fixed: Integration test now verifies X-RateLimit-* headers present
- L1 Fixed: `get_subnet_rate_limits` returns defensive copy for all subnets
- L2 Fixed: Lua source cached at module load time
- Code review round 2 (2026-03-14): 2 MEDIUM, 2 LOW — all fixed
- M1 Fixed: Added tests for `enforce_rate_limit` (allowed + raises RateLimitExceededError)
- M2 Fixed: Added test verifying rate limit headers on non-429 error responses (H3 path)
- L1 Fixed: Removed redundant `_flush_rate_keys` fixture (conftest already handles `rate:*`)
- All 409 tests pass (22 rate limit + 387 existing), ruff clean, mypy clean
- Task 1: Created `scripts/rate_limit.lua` — atomic Lua script handling 3 time windows (minute/day/month) with INCR + conditional EXPIRE
- Task 2: Created `gateway/middleware/rate_limit.py` — `check_rate_limit()` function with `RateLimitResult` dataclass, `to_headers()`, fail-open on Redis unavailability
- Task 3: Rate limit config defined as `_SUBNET_RATE_LIMITS` dict keyed by netuid with `get_subnet_rate_limits()` accessor
- Task 4: Replaced old per-endpoint rate limiting in chat.py, images.py, code.py with new multi-window per-key×per-subnet system. Updated `RateLimitExceededError` to carry `subnet` and `retry_after`. Updated error handler to include `retry_after` in 429 response body and `Retry-After` header
- Task 5: 19 new tests covering all ACs — multi-window enforcement, per-subnet/per-key independence, atomicity, response headers, 429 error format, Redis unavailability, integration
- All 406 tests pass (19 new + 387 existing), ruff clean, mypy clean

### Change Log

- 2026-03-14: Story 3.1 implementation complete — multi-window rate limiting engine

### File List

New files:
- scripts/rate_limit.lua — atomic multi-window Lua rate limiter (check-before-increment)
- gateway/middleware/rate_limit.py — RateLimitResult, check_rate_limit, enforce_rate_limit, get_subnet_rate_limits
- tests/middleware/test_rate_limit.py — 22 tests covering all ACs

Modified files:
- gateway/core/exceptions.py — RateLimitExceededError with subnet (str|None) and retry_after
- gateway/middleware/error_handler.py — retry_after in 429 body, Retry-After header, rate limit headers from request.state
- gateway/api/chat.py — uses enforce_rate_limit, stores rate_result on request.state, headers on all responses
- gateway/api/images.py — uses enforce_rate_limit, stores rate_result on request.state, headers on all responses
- gateway/api/code.py — uses enforce_rate_limit, stores rate_result on request.state, headers on all responses
- tests/conftest.py — added rate:* cleanup pattern
- tests/api/test_code.py — updated 429 test to use new subnet rate limits
