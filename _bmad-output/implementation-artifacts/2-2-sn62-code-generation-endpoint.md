# Story 2.2: SN62 Code Generation Endpoint

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to send code generation requests and receive generated code,
So that I can integrate AI code generation into my tools through the same gateway.

## Acceptance Criteria

1. **Given** I am authenticated with a valid API key, **when** I send `POST /v1/code/completions` with prompt, target programming language, and optional context, **then** the gateway translates my request into a CodeSynapse, **and** routes it to a selected SN62 miner via Dendrite, **and** returns generated code as a string with language identifier in the response (FR12, FR13).

2. **Given** the gateway starts up, **when** the FastAPI lifespan initializes, **then** the metagraph for SN62 is synced alongside SN1 and SN19, **and** the SN62 hotkey is loaded from the configured wallet path, **and** the metagraph background sync task covers SN1, SN19, and SN62.

3. **Given** a miner returns an invalid code response, **when** the SN62 adapter processes the response, **then** the output is validated and sanitized against the expected schema, **and** invalid responses result in a 502 error with miner UID in metadata.

4. **Given** all SN62 miners are unavailable, **when** the miner selector finds no eligible miners for SN62, **then** I receive a 503 with a clear message about SN62 unavailability, **and** SN1 and SN19 endpoints remain fully functional (NFR23).

5. **Given** normal code generation request handling, **when** measuring gateway-added overhead (excluding miner response time), **then** p95 overhead is under 200ms (NFR1).

## Tasks / Subtasks

- [x] Task 1: Config & infrastructure (AC: #2)
  - [x] 1.1: Add `sn62_netuid: int = 62` to `Settings` in `gateway/core/config.py`
  - [x] 1.2: Add `sn62_timeout_seconds: int = 30` to `Settings` — code generation uses same timeout as text (unlike image generation's 90s)
  - [x] 1.3: Add `code_rate_limit_per_minute: int = 60` to `Settings` for code endpoint rate limiting

- [x] Task 2: Pydantic schemas (AC: #1, #3)
  - [x] 2.1: Create `gateway/schemas/code.py` with `CodeCompletionRequest` — fields: `model` (str, min_length=1, max_length=64, default="tao-sn62"), `prompt` (str, min_length=1, max_length=16000 — code prompts can be longer), `language` (str, min_length=1, max_length=32 — target programming language, e.g. "python", "javascript"), `context` (str | None, max_length=32000 — optional additional context like existing code)
  - [x] 2.2: Create `CodeCompletionResponse` — fields: `id` (str), `object` (Literal["code.completion"]), `created` (int), `model` (str), `choices` (list[CodeChoice])
  - [x] 2.3: Create `CodeChoice` — fields: `index` (int), `code` (str), `language` (str), `finish_reason` (str)

- [x] Task 3: SN62 adapter (AC: #1, #3, #5)
  - [x] 3.1: Create `gateway/subnets/sn62_code.py` with `CodeSynapse(bt.Synapse)` — fields: `prompt` (str), `language` (str), `context` (str), response fields: `code` (str), `completion_language` (str). Set `required_hash_fields = ["prompt"]`.
  - [x] 3.2: Implement `SN62CodeAdapter(BaseAdapter)` with all 4 abstract methods:
    - `to_synapse(request_data)` -> Creates `CodeSynapse` from request
    - `from_response(synapse, request_data)` -> Converts miner response to `CodeCompletionResponse` dict with code, language, and completion ID
    - `sanitize_output(response_data)` -> Sanitizes code string with `self.sanitize_text()` (strip HTML tags from miner output — code itself is returned as-is, but HTML injection in surrounding text is prevented)
    - `get_config()` -> Returns `AdapterConfig(netuid=settings.sn62_netuid, subnet_name="sn62", timeout_seconds=settings.sn62_timeout_seconds)`
  - [x] 3.3: Code generation is NOT streaming — do NOT implement `to_streaming_synapse()`, `format_stream_chunk()`, or `format_stream_done()`. The base class defaults (`NotImplementedError`) are correct.

- [x] Task 4: Route handler (AC: #1, #4)
  - [x] 4.1: Create `gateway/api/code.py` with `POST /code/completions` route. Follow `images.py` pattern: `Depends(get_current_api_key)`, rate limit via `check_rate_limit`, call `adapter.execute()`, validate response against `CodeCompletionResponse`, return `JSONResponse` with gateway headers.
  - [x] 4.2: Retrieve adapter via `request.app.state.adapter_registry.get_by_model(body.model)` — raises `SubnetUnavailableError` (503) if not registered.
  - [x] 4.3: Log `code_completion_request` at start, `code_completion_success` / `code_completion_error` at completion with structlog.
  - [x] 4.4: No streaming path needed for code generation.

- [x] Task 5: App wiring (AC: #2)
  - [x] 5.1: In `gateway/main.py` lifespan, register SN62 with metagraph: `metagraph_manager.register_subnet(settings.sn62_netuid)`
  - [x] 5.2: After metagraph sync, add null check for SN62 metagraph (same pattern as SN1/SN19)
  - [x] 5.3: Register adapter: `adapter_registry.register(SN62CodeAdapter(), model_names=["tao-sn62"])`
  - [x] 5.4: In `gateway/api/router.py`, include code router: `router.include_router(code_router, prefix="/v1", tags=["Code Generation"])`

- [x] Task 6: Tests (AC: all)
  - [x] 6.1: Create `tests/subnets/test_sn62.py` — test `CodeSynapse` creation, `to_synapse()` conversion, `from_response()` output format, `sanitize_output()` strips HTML from code/language fields, `get_config()` returns correct netuid/timeout.
  - [x] 6.2: Create `tests/api/test_code.py` — integration tests: successful generation (mock dendrite returns valid code), verify response matches `CodeCompletionResponse` schema, verify gateway headers present, verify 422 for malformed requests (missing prompt, missing language), verify 503 when no SN62 adapter registered, verify 401 without auth, verify rate limiting works, verify 504 on timeout, verify 502 on invalid miner response.
  - [x] 6.3: Create `tests/schemas/test_code_schemas.py` — `CodeCompletionRequest` validation (prompt constraints, language required, context optional), `CodeCompletionResponse` validation, `CodeChoice` fields.
  - [x] 6.4: Update `tests/conftest.py` — register subnet 62 in `_test_metagraph_manager`, register `SN62CodeAdapter` in `_test_adapter_registry`, add `code_rate:*` to Redis cleanup patterns.
  - [x] 6.5: Verify `uv run pytest` passes with all new + existing tests (target: ~320+ tests).
  - [x] 6.6: Verify `uv run ruff check gateway/ tests/` and `uv run mypy gateway/` pass with zero errors on new code.

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Fat Base / Thin Adapter Pattern

SN62 adapter should be ~50-80 lines of code. The `BaseAdapter.execute()` method already handles:
- Miner selection via `MinerSelector.select_miner(netuid)`
- Dendrite query via `dendrite.forward(axons=[axon], synapse=synapse, timeout=timeout)`
- Timeout -> `MinerTimeoutError` (504), other failures -> `MinerInvalidResponseError` (502)
- Response validation (`is_timeout`, `is_success` checks)
- Gateway headers (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`)

The concrete adapter only provides:
- `to_synapse()`: API request -> `CodeSynapse`
- `from_response()`: Miner synapse -> API response dict
- `sanitize_output()`: Sanitize miner output before returning
- `get_config()`: Return `AdapterConfig` with netuid=62, name="sn62", timeout=30s

#### SN62 Synapse Protocol

**CRITICAL:** The exact Synapse fields for SN62 depend on the subnet's protocol. The Bittensor SDK uses Pydantic v2 for Synapse models. The CodeSynapse should follow the SN62 miner protocol:

```python
class CodeSynapse(bt.Synapse):
    """SN62 code generation synapse."""
    prompt: str = ""
    language: str = ""       # Target programming language
    context: str = ""        # Optional additional context (existing code, etc.)
    # Response fields (populated by miner)
    code: str = ""           # Generated code
    completion_language: str = ""  # Language of the generated code
    required_hash_fields: list[str] = ["prompt"]
```

**NOTE:** Research the actual SN62 (Ridges) protocol before implementation. The fields above are based on PRD requirements (FR12: prompt + target language + optional context; FR13: code string + language identifier) and may need adjustment based on the actual subnet protocol. Check the Bittensor SN62 docs or subnet repo for the exact Synapse definition.

#### Code Response Format

The response follows a completion-style format:

```json
{
  "id": "codecmpl-abc123...",
  "object": "code.completion",
  "created": 1234567890,
  "model": "tao-sn62",
  "choices": [
    {
      "index": 0,
      "code": "def hello():\n    print('Hello, world!')",
      "language": "python",
      "finish_reason": "stop"
    }
  ]
}
```

**Key requirements:**
- `id` is generated via a utility similar to `generate_completion_id()` but with `"codecmpl-"` prefix
- `created` is Unix timestamp
- `choices` is an array (even for single completions)
- `code` is the raw generated code string
- `language` echoes the requested language or miner's detected language
- `finish_reason` is "stop" for completed generation

#### Response Validation and Sanitization

**CRITICAL for code output:**
1. Validate that `code` is a non-empty string — empty code means miner failed -> `MinerInvalidResponseError`
2. Sanitize `code` and `completion_language` with `self.sanitize_text()` — strip HTML tags (miner content is untrusted). This strips `<script>`, `<iframe>`, etc. but preserves code content (angle brackets in code like `vector<int>` will be preserved since `nh3.clean()` keeps text content)
3. Do NOT truncate or modify the code content beyond HTML sanitization — developers need the complete output

#### Timeout Configuration

Code generation uses `sn62_timeout_seconds=30` (same as text generation's `dendrite_timeout_seconds=30`). Code generation timing is similar to text generation, unlike image generation which takes 10-30s miner-side. The PRD specifies <200ms p95 gateway overhead (NFR1) — same target as SN1.

#### API Endpoint Path

The endpoint is `POST /v1/code/completions` per the PRD and architecture doc.

#### Rate Limiting

Follow the same pattern as `images.py` and `chat.py`:
```python
async def _rate_limit_code(api_key: ApiKeyInfo) -> None:
    key = f"code_rate:{api_key.key_id}"
    result = await check_rate_limit(
        key=key,
        limit=settings.code_rate_limit_per_minute,
        window_seconds=60,
        fallback_limit=settings.code_rate_limit_per_minute,
        log_prefix="code_rate_limit",
    )
    if result == -1:
        raise RateLimitExceededError("Code generation rate limit exceeded.")
    if result is not None and result > settings.code_rate_limit_per_minute:
        raise RateLimitExceededError("Code generation rate limit exceeded.")
```

#### Error Handling

Uses the existing `GatewayError` hierarchy — no new exception types needed:
- `MinerTimeoutError` (504): Miner didn't respond within 30s
- `MinerInvalidResponseError` (502): Miner returned invalid/empty code
- `SubnetUnavailableError` (503): No SN62 miners available
- `RateLimitExceededError` (429): Rate limit exceeded
- `AuthenticationError` (401): Invalid API key

### Previous Story Intelligence (Story 2.1)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Error envelope format via `GatewayError` hierarchy + `gateway_exception_handler`
- Response validated against Pydantic schema before returning (e.g., `CodeCompletionResponse.model_validate(response_data)`)
- `nh3.clean()` for text sanitization — strip all HTML tags from miner output
- `TimeoutError` -> `MinerTimeoutError` (504), other exceptions -> `MinerInvalidResponseError` (502)
- `enable_bittensor=False` path: `app.state.dendrite=None`, `app.state.miner_selector=None`, empty `AdapterRegistry`
- `from_response()` takes `request_data` to echo the requested model name

**Learnings from adversarial code reviews (3 rounds, 28 issues on Story 2.1):**
- Sanitize ALL miner-provided text fields (code and language are untrusted)
- Always validate outgoing data against Pydantic schemas
- Distinguish timeout errors from other failures (different status codes)
- Test all error paths with integration tests, not just unit tests
- Use `nh3` for HTML sanitization — the project already has it as a dependency
- Restrict field values with `Literal` types where possible (e.g., `finish_reason`)
- Validate request field formats with `@model_validator` (e.g., language should be a recognized programming language identifier)

**Git intelligence — recent patterns (last 10 commits):**
- Test count: 278 tests passing as of latest commit
- Security hardening applied: body size limits, rate limiting, input validation
- Pre-existing ruff/mypy issues in `redis.py` and `api_keys.py` — do not fix (out of scope)
- SN19 adapter completed: 81 new tests, 270 total after Story 2.1 implementation, 278 after code reviews

### Library & Framework Requirements

| Library | Version | Why |
|---|---|---|
| `bittensor` | v10.1.0 (already installed) | `bt.Synapse`, `dendrite.forward()` |
| `fastapi` | 0.135.1 (already installed) | Route handlers, `JSONResponse` |
| `pydantic` | v2 (already installed) | Schema validation |
| `structlog` | (already installed) | Structured logging |
| `nh3` | (already installed) | HTML sanitization for code/language output |
| `httpx` | (dev, already installed) | Test client |

No new dependencies needed — everything is already in pyproject.toml.

### Project Structure Notes

**New files:**
- `gateway/schemas/code.py` — `CodeCompletionRequest`, `CodeCompletionResponse`, `CodeChoice`
- `gateway/subnets/sn62_code.py` — `CodeSynapse(bt.Synapse)`, `SN62CodeAdapter(BaseAdapter)`
- `gateway/api/code.py` — `POST /v1/code/completions` route handler

**Modified files:**
- `gateway/core/config.py` — Add `sn62_netuid`, `sn62_timeout_seconds`, `code_rate_limit_per_minute`
- `gateway/main.py` — Register SN62 subnet and adapter
- `gateway/api/router.py` — Include code router

**New test files:**
- `tests/subnets/test_sn62.py`
- `tests/api/test_code.py`
- `tests/schemas/test_code_schemas.py`

**Modified test files:**
- `tests/conftest.py` — Register subnet 62, SN62 adapter, add `code_rate:*` cleanup

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.2] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/prd.md#FR12] — Code generation requests with prompt, language, context
- [Source: _bmad-output/planning-artifacts/prd.md#FR13] — Code response as string with language identifier
- [Source: _bmad-output/planning-artifacts/prd.md#NFR1] — <200ms p95 gateway overhead for SN62
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Adapter pattern, error handling
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure] — `gateway/subnets/sn62_code.py`, `gateway/api/code.py`, `gateway/schemas/code.py`
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation-Patterns] — Naming conventions, async patterns, logging, DI
- [Source: _bmad-output/implementation-artifacts/2-1-sn19-image-generation-endpoint.md] — Previous story patterns, review learnings, 278 tests passing
- [Source: _bmad-output/planning-artifacts/prd.md#Rate-Limiting] — SN62: 10/min, 100/day, 1,000/month (free tier)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- Created `CodeSynapse(bt.Synapse)` with prompt, language, context request fields and code, completion_language response fields
- Implemented `SN62CodeAdapter(BaseAdapter)` — thin adapter (~75 lines) with all 4 abstract methods: `to_synapse()`, `from_response()`, `sanitize_output()`, `get_config()`
- Code ID generation uses `codecmpl-` prefix (separate from `chatcmpl-` used by SN1)
- Text sanitization: language field stripped via `nh3.clean()`; code field NOT sanitized (nh3 mangles angle brackets — see code review round 1)
- Created Pydantic schemas: `CodeCompletionRequest`, `CodeCompletionResponse`, `CodeChoice` — completion-style format with `Literal` types for `object` and `finish_reason`
- Created route handler at `POST /v1/code/completions` with auth, rate limiting, schema validation, structured logging
- Wired SN62 into app lifespan: metagraph registration, null check, adapter registry with model name `tao-sn62`
- Added `sn62_netuid=62`, `sn62_timeout_seconds=30`, `code_rate_limit_per_minute=60` to Settings
- 327 tests pass (49 new + 278 existing), zero regressions, ruff clean, mypy clean

### File List

New files:
- gateway/schemas/code.py
- gateway/subnets/sn62_code.py
- gateway/api/code.py
- tests/schemas/test_code_schemas.py
- tests/subnets/test_sn62.py
- tests/api/test_code.py

Modified files:
- gateway/core/config.py
- gateway/main.py
- gateway/api/router.py
- tests/conftest.py

### Change Log

- 2026-03-13: Implemented Story 2.2 — SN62 code generation endpoint with CodeSynapse, thin adapter, Pydantic schemas, route handler, app wiring, HTML sanitization. 324 tests passing (46 new).
- 2026-03-13: Code review round 1 (Claude Opus 4.6) — 4 issues found (1 HIGH, 2 MEDIUM, 1 LOW). All fixed: removed nh3 sanitization from code field (mangles angle brackets), added rate limit 429 integration test, fixed falsy guard in sanitize_output. 327 tests passing.

## Senior Developer Review (AI)

### Round 1

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested -> All Fixed

- [x] [HIGH] H1: `sanitize_text()` (nh3.clean) destroys code content — angle brackets mangled, generics stripped. Removed nh3 from code field, kept on language only.
- [x] [MEDIUM] M1: Missing rate limit integration test — added `test_code_completion_429_rate_limit`
- [x] [MEDIUM] M2: `sanitize_output` falsy guard skips empty-string code — changed to `is not None` check on language, removed code sanitization entirely
- [x] [LOW] L1: Story Dev Notes contained incorrect claim about nh3 preserving angle brackets — noted in completion notes

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 1 |
| **Total** | **4** |
