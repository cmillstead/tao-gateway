# Story 3.3: Security Hardening

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want all API keys redacted from logs, TLS enforced on all endpoints, and no request content logged by default,
So that the gateway meets production security standards.

## Acceptance Criteria

1. **Given** any log entry produced by the gateway
   **When** an API key value appears in the log context
   **Then** structlog redaction processors replace it with a masked value (e.g., `tao_sk_live_****`) (FR33)
   **And** wallet keys and other sensitive credentials are also redacted (NFR13)

2. **Given** the structlog configuration
   **When** I review all log output paths (request lifecycle, errors, background tasks)
   **Then** no full API key, wallet key, or credential appears in any log level
   **And** only the key prefix (first 12 chars) is used for identification in logs

3. **Given** the production deployment
   **When** a client connects to the gateway
   **Then** Caddy enforces TLS 1.2+ on all endpoints (FR36, NFR10)
   **And** plaintext HTTP requests are redirected to HTTPS
   **And** the Caddyfile is configured with auto-TLS via Let's Encrypt

4. **Given** the default logging policy
   **When** a request is processed
   **Then** only metadata is logged: timestamp, API key prefix, subnet, endpoint, miner UID, latency, status code, token count (FR41)
   **And** request body and response body content are never logged unless debug mode is enabled for that key

## Tasks / Subtasks

- [x] Task 1: Harden structlog redaction processor (AC: #1, #2)
  - [x] 1.1 Add missing sensitive patterns to `_SENSITIVE_PATTERNS` in `gateway/core/logging.py`: `mnemonic`, `seed`, `private_key`, `access_token`, `refresh_token`
  - [x] 1.2 Add value-based redaction: scan string values in event_dict for patterns matching `tao_sk_live_`, `tao_sk_test_`, JWT-like tokens (`eyJ...`), and connection strings (`postgresql://`, `redis://` with credentials)
  - [x] 1.3 Increase depth limit from 5 to 10 in `_redact_value()` OR convert to iterative approach with cycle detection
  - [x] 1.4 Add `repr=False` to sensitive fields in `gateway/core/config.py` Settings class (`database_url`, `redis_url`, `jwt_secret_key`) using Pydantic's `Field(repr=False)` to prevent accidental exposure in tracebacks
  - [x] 1.5 Sanitize exception messages in `internal_exception_handler` before logging: strip any substrings matching DB URLs, JWT secrets, or API key patterns from `str(exc)` before passing to `logger.error()`

- [x] Task 2: Audit and fix all log call sites (AC: #2, #4)
  - [x] 2.1 Fix structlog anti-pattern in `gateway/core/rate_limit.py:116` — replace f-string interpolation with structured key-value logging
  - [x] 2.2 Audit all 50+ log statements across the codebase to verify none log request/response body content by default
  - [x] 2.3 Verify every log statement uses only: API key prefix (12 chars), subnet ID, miner UID (8-char hotkey prefix), endpoint path, latency, status code, token count — never raw keys, passwords, or content

- [x] Task 3: Add security response headers middleware (AC: #3)
  - [x] 3.1 Create security headers middleware in `gateway/middleware/security_headers.py`
  - [x] 3.2 Add headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HSTS), `Content-Security-Policy: default-src 'self'`, `X-XSS-Protection: 0` (disabled per OWASP recommendation — CSP replaces it)
  - [x] 3.3 Register middleware in `gateway/main.py`
  - [x] 3.4 HSTS header only injected when `settings.debug` is False (don't enforce HTTPS in local dev)

- [x] Task 4: Create Caddyfile for TLS termination (AC: #3)
  - [x] 4.1 Create `Caddyfile` at project root with auto-TLS via Let's Encrypt
  - [x] 4.2 Configure reverse proxy to `localhost:8000` (uvicorn)
  - [x] 4.3 Enforce TLS 1.2+ minimum protocol version
  - [x] 4.4 Redirect HTTP to HTTPS
  - [x] 4.5 Add security headers at Caddy layer as defense-in-depth (supplement, not replace, the application middleware)

- [x] Task 5: Verify metadata-only default logging policy (AC: #4)
  - [x] 5.1 Audit all route handlers (`chat.py`, `images.py`, `code.py`) to confirm request body content is never logged
  - [x] 5.2 Audit all adapter code (`subnets/base.py`, `sn1_text.py`, `sn19_image.py`, `sn62_code.py`) to confirm response content is never logged
  - [x] 5.3 Document the metadata-only fields that ARE logged at each log call site
  - [x] 5.4 If any log call logs content, remove it or gate behind a debug-mode check

- [x] Task 6: Write tests (AC: all)
  - [x] 6.1 Test value-based redaction: API key pattern in string values is masked
  - [x] 6.2 Test value-based redaction: JWT-like token in string values is masked
  - [x] 6.3 Test value-based redaction: connection string with credentials in string values is masked
  - [x] 6.4 Test new sensitive patterns (`mnemonic`, `seed`, `private_key`, `access_token`, `refresh_token`) are redacted
  - [x] 6.5 Test Settings `repr` does not expose `database_url`, `redis_url`, `jwt_secret_key`
  - [x] 6.6 Test `internal_exception_handler` sanitizes exception messages containing DB URLs or API keys
  - [x] 6.7 Test security headers middleware returns all expected headers
  - [x] 6.8 Test security headers middleware omits HSTS in debug mode
  - [x] 6.9 Integration test: make a real API request and capture log output to verify no sensitive data appears
  - [x] 6.10 Test Caddyfile parses correctly: `caddy validate --config Caddyfile` (if caddy available in CI)

## Dev Notes

### Architecture Patterns and Constraints

- **Structlog is MANDATORY** — never use `print()` or stdlib `logging`. All logging via structlog bound loggers. [Source: architecture.md#Logging]
- **Key redaction pattern:** First 12 chars of API key prefix only. Format: `tao_sk_live_****`. [Source: architecture.md#Logging]
- **Error envelope format** for any error responses — already implemented in Story 3.2. Do not modify. [Source: architecture.md#Format Patterns]
- **Dependency injection:** Use `Depends()` for request-scoped, `app.state` for singletons. [Source: architecture.md#Dependency Injection]
- **Security headers at both Caddy and application layer** — defense-in-depth. Caddy is the primary TLS terminator; application middleware adds headers as a safety net.

### Existing Code to Leverage — DO NOT REINVENT

- **`gateway/core/logging.py`** — Structlog redaction processor with 13 sensitive patterns and recursive dict/list redaction. EXTEND this, do not replace. The `_redact_sensitive_keys()` processor is already in the structlog pipeline.
- **`gateway/middleware/auth.py`** — Already properly redacts API key prefixes before logging. Do not modify auth logging unless a specific gap is found.
- **`gateway/core/redis.py:41`** — Already strips credentials from Redis URL before logging (`url.split("@")[-1]`). Good pattern to follow.
- **`gateway/core/config.py`** — Settings class with `database_url`, `redis_url`, `jwt_secret_key`. JWT secret validation already rejects insecure defaults in production.
- **`gateway/middleware/error_handler.py`** — `internal_exception_handler` logs `error=str(exc)`. This is the primary value-leakage risk — exception messages can contain DB URLs, JWT secrets, or API keys.
- **`gateway/main.py`** — Current middleware order: CORS → body size limit → exception handlers. Security headers middleware should be added to this chain.
- **`tests/core/test_logging.py`** — 69 lines of existing tests for redaction. Extend, don't rewrite.

### Security Gaps Found During Analysis

1. **Value-based redaction missing:** `_redact_sensitive_keys()` only redacts by key name. If `error=str(exc)` contains `postgresql://user:password@host/db`, it passes through unredacted. MUST add value-based pattern scanning.

2. **Missing sensitive patterns:** `mnemonic`, `seed`, `private_key`, `access_token`, `refresh_token` not in `_SENSITIVE_PATTERNS`. These could appear in Bittensor SDK exceptions.

3. **Settings repr unprotected:** If `Settings` object appears in a traceback or log, `database_url` and `jwt_secret_key` are visible. Pydantic v2 supports `Field(repr=False)`.

4. **No security response headers:** Missing `X-Content-Type-Options`, `Strict-Transport-Security`, `X-Frame-Options`, `Content-Security-Policy`. These prevent MIME sniffing, clickjacking, and XSS.

5. **No Caddyfile:** Architecture specifies Caddy for TLS termination with ~5 lines of config. Not yet created.

6. **f-string in structlog call:** `gateway/core/rate_limit.py:116` uses f-string interpolation which bypasses structured logging. Minor issue but should be fixed.

7. **Depth limit of 5:** `_redact_value()` stops recursing at depth 5. Deeply nested payloads could leak sensitive data. Increase or remove limit.

### What NOT to Touch

- Do NOT modify the error envelope format (Story 3.2 owns this)
- Do NOT modify rate limiting logic (Story 3.1 owns this)
- Do NOT modify auth flow or API key generation (Epic 1 owns this)
- Do NOT add request/response content logging — the default is metadata-only and that's correct
- Do NOT modify the exception hierarchy in `core/exceptions.py`

### Project Structure Notes

- New files: `gateway/middleware/security_headers.py`, `Caddyfile`
- Modified files: `gateway/core/logging.py`, `gateway/core/config.py`, `gateway/middleware/error_handler.py`, `gateway/core/rate_limit.py`, `gateway/main.py`
- Test files: extend `tests/core/test_logging.py`, add `tests/middleware/test_security_headers.py`
- File structure follows existing conventions: middleware in `gateway/middleware/`, tests mirror source tree

### Testing Standards

- **Real Postgres and Redis required** — use Docker test containers, never mock
- **Mock only Bittensor SDK** — everything else uses real infrastructure
- Run: `uv run pytest --tb=short -q`
- Lint: `uv run ruff check gateway/ tests/`
- Types: `uv run mypy gateway/`
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests
- 426 tests currently pass (as of Story 3.2) — this story must not break any existing tests

### Previous Story Intelligence (Story 3.2)

- **Error handler exception logging risk** — `internal_exception_handler` logs `error=str(exc)` at error level. This is the primary vector for sensitive data leakage via exception messages. Story 3.3 must sanitize these before logging.
- **21 error handler tests written** — Story 3.2 wrote comprehensive error handler tests. Do not break these. Add sanitization INSIDE the handler, preserving the existing response behavior.
- **Code review found 6 issues in Story 3.2** — expect similar scrutiny. Write clean code first time.
- **All 426 tests pass** — baseline for regression testing.

### Git Intelligence (Recent Commits)

- `33eacdf` Merge PR #28: Story 3.2 error handling and response metadata
- `7107eba` feat: add error handling, validation errors, and response metadata (Story 3.2)
- `6f090d3` Merge PR #27: Story 3.1 rate limiting engine
- `8d04b30` feat: add multi-window per-key×per-subnet rate limiting engine (Story 3.1)
- `4b21549` fix: address code review findings — 28 issues across security, bugs, code quality
- Pattern: security-conscious development with thorough code review. Each story followed by review fixes.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#Logging, Security, Infrastructure & Deployment]
- [Source: _bmad-output/planning-artifacts/prd.md#FR33, FR36, FR41, NFR10, NFR13]
- [Source: gateway/core/logging.py — Existing redaction processor]
- [Source: gateway/core/config.py — Settings with sensitive fields]
- [Source: gateway/middleware/error_handler.py — internal_exception_handler with str(exc) logging]
- [Source: gateway/middleware/auth.py — API key redaction pattern]
- [Source: gateway/core/redis.py — URL credential stripping pattern]
- [Source: tests/core/test_logging.py — Existing redaction tests]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Hardened structlog redaction — added 5 new sensitive key patterns (`mnemonic`, `seed`, `private_key`, `access_token`, `refresh_token`), added value-based redaction via regex for API keys, JWTs, and credential URLs in string values, increased depth limit from 5 to 10, added `Field(repr=False)` to `database_url`/`redis_url`/`jwt_secret_key` in Settings, sanitized exception messages in `internal_exception_handler` via `_redact_string_value()`
- Task 2: Fixed f-string structlog anti-pattern in `rate_limit.py:116`, audited all 50+ log statements — confirmed metadata-only logging with no content leakage
- Task 3: Created `SecurityHeadersMiddleware` with `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Content-Security-Policy`, and conditional HSTS (production only). Registered in `main.py`.
- Task 4: Created `Caddyfile` with auto-TLS (Let's Encrypt), TLS 1.2+ minimum, reverse proxy to localhost:8000, security headers as defense-in-depth
- Task 5: Verified metadata-only logging policy — no route handler or adapter logs request/response body content
- Task 6: 19 new tests across `test_logging.py` (17 tests), `test_security_headers.py` (2 tests), and `test_error_handler.py` (2 tests). All 445 tests pass, ruff clean, mypy clean.

### Change Log

- 2026-03-14: Story 3.3 implementation complete — security hardening across log redaction, security headers, TLS config, and metadata-only logging verification
- 2026-03-14: Code review — 5 issues fixed (1 HIGH, 3 MEDIUM, 1 LOW): narrowed `seed` → `seed_phrase` pattern, added `_SAFE_KEYS` skip for event/level/timestamp, converted to pure ASGI middleware, added integration log test, added `Referrer-Policy` header
- 2026-03-14: Code review #2 — 5 issues fixed (2 HIGH, 3 MEDIUM): string redaction now applied before depth check in `_redact_value`, replaced broad `"token"` pattern with specific `auth_token`/`bearer_token`/`session_token` to avoid masking `token_count` metadata, renamed `_redact_string_value` → `redact_string_value` (public API), added `Referrer-Policy` to Caddyfile, removed redundant `access_token`/`refresh_token` patterns (now needed after token fix)

### File List

New files:
- gateway/middleware/security_headers.py — SecurityHeadersMiddleware with X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP, conditional HSTS, Referrer-Policy
- Caddyfile — TLS termination config with auto-TLS, TLS 1.2+, reverse proxy, security headers including Referrer-Policy
- tests/middleware/test_security_headers.py — 3 tests for security headers presence, HSTS debug-mode, and error response headers

Modified files:
- gateway/core/logging.py — Added 5 sensitive patterns, value-based redaction (`redact_string_value`), string redaction before depth check, specific token patterns replacing broad `"token"`, `_SAFE_KEYS` optimization
- gateway/core/config.py — Added `Field(repr=False)` to `database_url`, `redis_url`, `jwt_secret_key`
- gateway/middleware/error_handler.py — Sanitize exception messages via `redact_string_value()` before logging
- gateway/core/rate_limit.py — Fixed f-string structlog anti-pattern to use structured key-value logging
- gateway/main.py — Registered SecurityHeadersMiddleware
- tests/core/test_logging.py — 20 new tests for value-based redaction, new patterns, token count safety, Settings repr, depth limit, string redaction beyond depth
- tests/middleware/test_error_handler.py — 3 new tests for exception message sanitization and integration log test
