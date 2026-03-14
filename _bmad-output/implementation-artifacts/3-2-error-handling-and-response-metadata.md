# Story 3.2: Error Handling & Response Metadata

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want clear, distinct error codes and debugging metadata in every response,
So that I can distinguish gateway issues from miner issues and troubleshoot effectively.

## Acceptance Criteria

1. **Given** a gateway-internal error occurs (e.g., database failure, configuration error)
   **When** the global exception handler catches it
   **Then** I receive a 500 response with `type: "internal_error"` in the error envelope
   **And** the error is distinguishable from upstream miner failures (FR24)

2. **Given** a miner returns an invalid response
   **When** the adapter detects the invalid response
   **Then** I receive a 502 response with `type: "bad_gateway"` and the miner UID in the error body

3. **Given** a miner times out
   **When** the Dendrite query exceeds the timeout threshold
   **Then** I receive a 504 response with `type: "gateway_timeout"` and the miner UID in the error body
   **And** the error is distinct from a gateway-side timeout (FR24)

4. **Given** any successful response from a subnet endpoint
   **When** the response is returned
   **Then** headers include `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, and `X-TaoGateway-Subnet` (FR25)

5. **Given** I send a malformed request body
   **When** Pydantic validation fails
   **Then** I receive a 422 response with field-level errors listing each invalid field, the constraint violated, and the value received (FR26)
   **And** the error follows the standard error envelope format

6. **Given** the typed exception hierarchy
   **When** any exception is raised in the gateway
   **Then** it maps to a specific HTTP status code and error type via the global exception handler
   **And** `GatewayError` subtypes include `MinerTimeoutError`, `MinerInvalidResponseError`, `SubnetUnavailableError`, `RateLimitExceededError`, `AuthenticationError`

## Tasks / Subtasks

- [x] Task 1: Create error response Pydantic schema (AC: #1, #5, #6)
  - [x] 1.1 Create `gateway/schemas/errors.py` with `ErrorDetail` and `ErrorResponse` models matching the architecture error envelope format
  - [x] 1.2 `ErrorDetail` fields: `type` (str), `message` (str), `code` (int), optional `subnet` (str|None), optional `retry_after` (int|None), optional `miner_uid` (str|None), optional `reason` (str|None)
  - [x] 1.3 `ErrorResponse` model: `error: ErrorDetail`
  - [x] 1.4 Unified `ErrorDetail` handles both standard errors and validation errors via optional `errors` field (list of field-level dicts)
  - [x] 1.5 Each field error dict: `field` (str — dot-path like "messages.0.role"), `message` (str — constraint violated), `value` (Any — the invalid value received)

- [x] Task 2: Add miner_uid to error responses for miner errors (AC: #2, #3)
  - [x] 2.1 Updated `gateway_exception_handler` to include `miner_uid` in error body for 502/504 status codes only (scoped SEC-018 exception)
  - [x] 2.2 miner_uid (8-char hotkey prefix) included in 502 and 504 responses; omitted from 429, 401, 500, 503
  - [x] 2.3 miner_uid still logged at warning level for all miner errors

- [x] Task 3: Add custom validation error handler (AC: #5)
  - [x] 3.1 Created `validation_exception_handler` in `error_handler.py`
  - [x] 3.2 Imports `RequestValidationError` from `fastapi.exceptions`
  - [x] 3.3 Transforms Pydantic errors into standard error envelope with field-level errors
  - [x] 3.4 Converts `loc` tuple to dot-path string, strips leading "body" segment
  - [x] 3.5 Registered in `main.py`: `app.add_exception_handler(RequestValidationError, validation_exception_handler)`

- [x] Task 4: Add catch-all handler for unhandled exceptions (AC: #1, #6)
  - [x] 4.1 Created `internal_exception_handler` returning 500 with `type: "internal_error"`
  - [x] 4.2 Logs full exception at error level with structlog (error_type, error, path, method)
  - [x] 4.3 Response body is generic: "An internal error occurred" — no internal details exposed
  - [x] 4.4 Registered in `main.py`: `app.add_exception_handler(Exception, internal_exception_handler)`

- [x] Task 5: Verify response metadata headers on success (AC: #4)
  - [x] 5.1 Audited chat.py, images.py, code.py — all pass `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet` through from adapter
  - [x] 5.2 Streaming responses include `X-TaoGateway-Miner-UID` and `X-TaoGateway-Subnet` (confirmed in base.py execute_stream)
  - [x] 5.3 No missing headers found — all already present

- [x] Task 6: Write tests (AC: all)
  - [x] 6.1 Rewrote `tests/middleware/test_error_handler.py` with 21 comprehensive tests
  - [x] 6.2 Test 500: `test_500_internal_error` + `test_catch_all_handler` — generic message, no stack trace
  - [x] 6.3 Test 502: `test_502_bad_gateway_includes_miner_uid` — type, miner_uid, subnet verified
  - [x] 6.4 Test 504: `test_504_gateway_timeout_includes_miner_uid` — type, miner_uid, subnet verified
  - [x] 6.5 Test 503: `test_503_subnet_unavailable` — type, subnet, reason verified
  - [x] 6.6 Test 422: `test_422_validation_error_via_handler` — field-level errors with field, message
  - [x] 6.7 Test 422 multiple: `test_422_multiple_field_errors` — both model and messages missing
  - [x] 6.8 Test 401: `test_401_authentication_error` — type: authentication_error
  - [x] 6.9 Test 429: `test_429_rate_limit_error` — subnet, retry_after, Retry-After header
  - [x] 6.10 Test headers: `test_success_response_has_gateway_headers` — verifies BaseAdapter.execute includes all three headers
  - [x] 6.11 Test envelope: `test_miner_uid_omitted_from_non_miner_errors` — non-miner errors never include miner_uid
  - [x] 6.12 Test schema: `test_all_errors_match_envelope_schema` — parametrized across all 6 error types, validates against ErrorResponse

## Dev Notes

### Architecture Patterns and Constraints

- **Error envelope format (MANDATORY):**
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
  `type` is machine-readable (`snake_case`), `message` is human-readable. [Source: architecture.md#Format Patterns]

- **Custom headers:** `X-TaoGateway-{Name}` format. Specifically: `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet` [Source: architecture.md#API Naming]

- **Exception hierarchy already exists:** `GatewayError` base with `MinerTimeoutError` (504), `MinerInvalidResponseError` (502), `SubnetUnavailableError` (503), `RateLimitExceededError` (429), `AuthenticationError` (401). Do NOT create new exception classes unless a genuinely new error category is discovered. [Source: gateway/core/exceptions.py]

- **Global exception handler already exists:** `gateway_exception_handler` in `error_handler.py` handles all `GatewayError` subtypes. Currently omits `miner_uid` from responses (SEC-018). This story requires adding miner_uid to 502/504 responses.

- **Dependency injection:** Use `Depends()` pattern, consistent with auth and rate limit middleware [Source: architecture.md#Dependency Injection]

- **Logging:** structlog only, never `print()` or stdlib `logging`. Log errors at `error` level, miner failures at `warning` level. [Source: architecture.md#Logging]

### Existing Code to Leverage — DO NOT REINVENT

- `gateway/core/exceptions.py` — Complete exception hierarchy. All needed types exist. Do NOT create duplicate exception classes.
- `gateway/middleware/error_handler.py` — `gateway_exception_handler()` already maps `GatewayError` to JSON with error envelope. Extend, don't replace.
- `gateway/subnets/base.py` — `execute()` returns `(response_data, gateway_headers)` with all three `X-TaoGateway-*` headers. `execute_stream()` returns headers with `Miner-UID` and `Subnet`.
- `gateway/api/chat.py`, `images.py`, `code.py` — All route handlers already pass gateway headers through to responses. Verify, don't rewrite.
- `gateway/main.py` — Already registers `GatewayError` exception handler. Add new handlers for `RequestValidationError` and `Exception` here.
- `gateway/middleware/rate_limit.py` — `RateLimitResult.to_headers()` already produces rate limit response headers.
- `tests/conftest.py` — Shared fixtures for test DB, Redis, app client. Reuse existing patterns.

### SEC-018 Reconciliation

The previous security scan (PR #22) established SEC-018: omit miner_uid from client-facing responses. However, Story 3.2 AC #2 and #3 explicitly require miner_uid in 502/504 error bodies. The miner_uid used is already a safe 8-character hotkey prefix (not a full key). Resolution: include `miner_uid` in 502 and 504 error bodies only (not in 429, 401, 500, 503). Update the comment in `error_handler.py` to document this scoped exception to SEC-018.

### Validation Error Transformation

FastAPI/Pydantic returns validation errors as:
```json
{
  "detail": [
    {
      "type": "string_type",
      "loc": ["body", "messages", 0, "role"],
      "msg": "Input should be a valid string",
      "input": 123,
      "ctx": {...}
    }
  ]
}
```

This must be transformed to match our error envelope:
```json
{
  "error": {
    "type": "validation_error",
    "message": "Request validation failed",
    "code": 422,
    "errors": [
      {
        "field": "messages.0.role",
        "message": "Input should be a valid string",
        "value": 123
      }
    ]
  }
}
```

Key transformations:
- `loc` tuple → dot-path string, strip leading "body" segment
- `msg` → `message`
- `input` → `value`
- Wrap in standard `{"error": {...}}` envelope

### Project Structure Notes

- New files: `gateway/schemas/errors.py`, `tests/middleware/test_error_handler.py`
- Modified files: `gateway/middleware/error_handler.py` (add miner_uid to 502/504, add validation handler, add catch-all), `gateway/main.py` (register new exception handlers)
- File structure follows existing conventions: schemas in `gateway/schemas/`, tests mirror source tree

### Testing Standards

- **Real Postgres and Redis required** — use Docker test containers, never mock
- **Mock only Bittensor SDK** — everything else uses real infrastructure
- Run: `uv run pytest --tb=short -q`
- Lint: `uv run ruff check gateway/ tests/`
- Types: `uv run mypy gateway/`
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests
- 409 tests currently pass — this story must not break any existing tests

### Previous Story Intelligence (Story 3.1)

- **Rate limit headers on error responses** — Story 3.1 added `rate_result.to_headers()` on error responses via `request.state.rate_limit_result`. The error handler already looks for this. Ensure new error handlers (validation, catch-all) don't break this path.
- **`enforce_rate_limit()` shared helper** — consolidation pattern from 3.1 review. Follow same consolidation approach if error handling logic is duplicated across handlers.
- **Lua script loaded at module level** — Lua source cached at module load time (3.1 review fix L2). No relevance to this story but shows pattern of avoiding repeated I/O.
- **Code review found 3 HIGH + 3 MEDIUM + 2 LOW issues in 3.1** — expect similar scrutiny. Write clean code the first time.

### Git Intelligence (Recent Commits)

- `8d04b30` feat: add multi-window per-key×per-subnet rate limiting engine (Story 3.1) — latest feature commit
- `4b21549` fix: address code review findings — 3 rounds, 28 issues across security, bugs, code quality
- `2b2ffbc` fix: address security scan findings — 22 issues across attack surface, data flow, supply chain
- Pattern: security-conscious development. Every response must follow the error envelope. Never expose internals.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 3, Story 3.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Error Handling, Format Patterns, API Naming, Cross-Cutting Concerns]
- [Source: _bmad-output/planning-artifacts/prd.md#FR24-FR26]
- [Source: gateway/core/exceptions.py — Complete exception hierarchy]
- [Source: gateway/middleware/error_handler.py — Existing global handler]
- [Source: gateway/subnets/base.py — X-TaoGateway-* header generation]
- [Source: gateway/main.py — Exception handler registration]
- [Source: gateway/api/chat.py — Route handler pattern with headers]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed — comprehensive developer guide created
- Task 1: Created `gateway/schemas/errors.py` with `ErrorDetail` and `ErrorResponse` Pydantic models — unified schema handles standard errors and validation errors via optional `errors` field
- Task 2: Updated `gateway_exception_handler` to include `miner_uid` in 502/504 responses only (scoped SEC-018 exception). Added `_MINER_ERROR_CODES` set for clarity. Non-miner errors (429, 401, 500, 503) still omit miner_uid.
- Task 3: Created `validation_exception_handler` — transforms Pydantic `RequestValidationError` into standard error envelope with field-level errors (field dot-path, message, value)
- Task 4: Created `internal_exception_handler` — catch-all for unhandled exceptions, returns generic 500 with no internal details, logs full exception with structlog
- Task 5: Audited all three subnet route handlers — all `X-TaoGateway-*` headers already present on success and streaming responses. No changes needed.
- Task 6: Rewrote `tests/middleware/test_error_handler.py` with 21 tests covering all ACs. Updated `tests/api/test_chat.py` to expect miner_uid in 504 responses (Story 3.2 requirement).
- All 426 tests pass (21 error handler + 405 existing), ruff clean, mypy clean
- Code review completed (2026-03-14): 1 HIGH, 3 MEDIUM, 2 LOW issues found — all fixed
- H1 Fixed: Added handler registration verification tests (`test_catch_all_handler_registered`, `test_validation_handler_registered`)
- M1 Fixed: Added `miner_uid` assertion to 502 test in `test_chat.py`
- M2 Fixed: Replaced weak conditional 422 integration tests with deterministic `test_422_validation_error_integration` using unparseable JSON
- M3 Fixed: Replaced source-inspection header test with handler registration tests
- L1 Fixed: Validation handler now strips "body", "query", and "path" prefixes from loc
- L2 Fixed: Added `RateLimitExceededError` to `test_miner_uid_omitted_from_non_miner_errors`
- All 426 tests pass after review fixes, ruff clean, mypy clean

### Change Log

- 2026-03-14: Story 3.2 implementation complete — error handling, validation errors, response metadata, catch-all handler
- 2026-03-14: Code review — 6 issues fixed (1 HIGH, 3 MEDIUM, 2 LOW)

### File List

New files:
- gateway/schemas/errors.py — ErrorDetail and ErrorResponse Pydantic schemas

Modified files:
- gateway/middleware/error_handler.py — Added miner_uid in 502/504, validation_exception_handler, internal_exception_handler, strips query/path prefixes
- gateway/main.py — Registered RequestValidationError and Exception handlers
- tests/middleware/test_error_handler.py — 21 tests: error handlers, validation, catch-all, handler registration, schema validation
- tests/api/test_chat.py — Updated 502 and 504 tests to expect miner_uid (Story 3.2 AC #2, #3)
