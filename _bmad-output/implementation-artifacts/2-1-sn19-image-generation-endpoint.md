# Story 2.1: SN19 Image Generation Endpoint

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to send image generation requests and receive generated images,
So that I can add AI image capabilities to my application through the same API key I use for text generation.

## Acceptance Criteria

1. **Given** I am authenticated with a valid API key, **when** I send `POST /v1/images/generate` with prompt text, resolution, and style parameters, **then** the gateway translates my request into an ImageGenSynapse, **and** routes it to a selected SN19 miner via Dendrite, **and** returns generated image data as base64-encoded PNG or image URL in the response (FR10, FR11).

2. **Given** the gateway starts up, **when** the FastAPI lifespan initializes, **then** the metagraph for SN19 is synced alongside SN1, **and** the SN19 hotkey is loaded from the configured wallet path, **and** the metagraph background sync task covers both SN1 and SN19.

3. **Given** a miner returns an invalid image response, **when** the SN19 adapter processes the response, **then** the output is validated against the expected image schema before returning, **and** invalid responses result in a 502 error with miner UID in metadata.

4. **Given** all SN19 miners are unavailable, **when** the miner selector finds no eligible miners for SN19, **then** I receive a 503 with a clear message about SN19 unavailability, **and** SN1 endpoints remain fully functional (NFR23).

5. **Given** normal image generation request handling, **when** measuring gateway-added overhead (excluding miner generation time), **then** p95 overhead is under 500ms (NFR2).

6. **Given** the SN19 endpoint, **when** a developer sends an image generation request, **then** the endpoint timeout is set generously (60-90 seconds) to accommodate miner-side generation time (typically 10-30 seconds), **and** API documentation clearly states expected response times for image generation vs. text/code endpoints.

## Tasks / Subtasks

- [x] Task 1: Config & infrastructure (AC: #2)
  - [x]1.1: Add `sn19_netuid: int = 19` to `Settings` in `gateway/core/config.py`
  - [x]1.2: Add `sn19_timeout_seconds: int = 90` to `Settings` — image generation requires longer timeout than text (10-30s miner-side generation)
  - [x]1.3: Add `images_rate_limit_per_minute: int = 30` to `Settings` for image endpoint rate limiting

- [x] Task 2: Pydantic schemas (AC: #1, #3)
  - [x]2.1: Create `gateway/schemas/images.py` with `ImageGenerationRequest` — fields: `model` (str, min_length=1, max_length=64, default="tao-sn19"), `prompt` (str, min_length=1, max_length=4000), `n` (int, default=1, ge=1, le=4 — number of images), `size` (str, default="1024x1024" — resolution), `style` (str, optional — "natural" or "vivid"), `response_format` (Literal["b64_json", "url"], default="b64_json")
  - [x]2.2: Create `ImageGenerationResponse` — fields: `created` (int), `data` (list of `ImageData`)
  - [x]2.3: Create `ImageData` — fields: `b64_json` (str | None), `url` (str | None), `revised_prompt` (str | None)

- [x] Task 3: SN19 adapter (AC: #1, #3, #5, #6)
  - [x]3.1: Create `gateway/subnets/sn19_image.py` with `ImageGenSynapse(bt.Synapse)` — fields will depend on SN19 protocol (prompt, resolution/size, style). Set `required_hash_fields = ["prompt"]`.
  - [x]3.2: Implement `SN19ImageAdapter(BaseAdapter)` with all 4 abstract methods:
    - `to_synapse(request_data)` → Creates `ImageGenSynapse` from request
    - `from_response(synapse, request_data)` → Converts miner response to `ImageGenerationResponse` dict with base64 image data
    - `sanitize_output(response_data)` → Validates image data is legitimate base64 (not executable content), sanitizes `revised_prompt` with `self.sanitize_text()`
    - `get_config()` → Returns `AdapterConfig(netuid=settings.sn19_netuid, subnet_name="sn19", timeout_seconds=settings.sn19_timeout_seconds)`
  - [x]3.3: Image generation is NOT streaming — do NOT implement `to_streaming_synapse()`, `format_stream_chunk()`, or `format_stream_done()`. The base class defaults (`NotImplementedError`) are correct.

- [x] Task 4: Route handler (AC: #1, #4, #6)
  - [x]4.1: Create `gateway/api/images.py` with `POST /images/generate` route. Follow `chat.py` pattern: `Depends(get_current_api_key)`, rate limit via `check_rate_limit`, call `adapter.execute()`, validate response against `ImageGenerationResponse`, return `JSONResponse` with gateway headers.
  - [x]4.2: Retrieve adapter via `request.app.state.adapter_registry.get_by_model(body.model)` — raises `SubnetUnavailableError` (503) if not registered.
  - [x]4.3: Log `image_generation_request` at start, `image_generation_success` / `image_generation_error` at completion with structlog.
  - [x]4.4: No streaming path needed for image generation.

- [x] Task 5: App wiring (AC: #2)
  - [x]5.1: In `gateway/main.py` lifespan, register SN19 with metagraph: `metagraph_manager.register_subnet(settings.sn19_netuid)`
  - [x]5.2: After metagraph sync, add null check for SN19 metagraph (same pattern as SN1)
  - [x]5.3: Register adapter: `adapter_registry.register(SN19ImageAdapter(), model_names=["tao-sn19"])`
  - [x]5.4: In `gateway/api/router.py`, include images router: `router.include_router(images_router, prefix="/v1", tags=["Image Generation"])`

- [x] Task 6: Tests (AC: all)
  - [x]6.1: Create `tests/subnets/test_sn19.py` — test `ImageGenSynapse` creation, `to_synapse()` conversion, `from_response()` output format, `sanitize_output()` strips dangerous content from revised_prompt, validates base64 data is not executable, `get_config()` returns correct netuid/timeout.
  - [x]6.2: Create `tests/api/test_images.py` — integration tests: successful generation (mock dendrite returns valid image data), verify response matches `ImageGenerationResponse` schema, verify gateway headers present, verify 422 for malformed requests (missing prompt, invalid size), verify 503 when no SN19 adapter registered, verify 401 without auth, verify rate limiting works.
  - [x]6.3: Create `tests/schemas/test_image_schemas.py` — `ImageGenerationRequest` validation (prompt constraints, size values, response_format values), `ImageGenerationResponse` validation, `ImageData` with b64_json vs url.
  - [x]6.4: Update `tests/conftest.py` — register subnet 19 in `_test_metagraph_manager`, register `SN19ImageAdapter` in `_test_adapter_registry`.
  - [x]6.5: Verify `uv run pytest` passes with all new + existing tests (target: ~210+ tests).
  - [x]6.6: Verify `uv run ruff check gateway/ tests/` and `uv run mypy gateway/` pass with zero errors on new code.

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Fat Base / Thin Adapter Pattern

SN19 adapter should be ~50 lines of code. The `BaseAdapter.execute()` method already handles:
- Miner selection via `MinerSelector.select_miner(netuid)`
- Dendrite query via `dendrite.forward(axons=[axon], synapse=synapse, timeout=timeout)`
- Timeout → `MinerTimeoutError` (504), other failures → `MinerInvalidResponseError` (502)
- Response validation (`is_timeout`, `is_success` checks)
- Gateway headers (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`)

The concrete adapter only provides:
- `to_synapse()`: API request → `ImageGenSynapse`
- `from_response()`: Miner synapse → API response dict
- `sanitize_output()`: Sanitize miner output before returning
- `get_config()`: Return `AdapterConfig` with netuid=19, name="sn19", timeout=90s

#### SN19 Synapse Protocol

**CRITICAL:** The exact Synapse fields for SN19 depend on the subnet's protocol. The Bittensor SDK uses Pydantic v2 for Synapse models. The ImageGenSynapse should follow the SN19 miner protocol:

```python
class ImageGenSynapse(bt.Synapse):
    """SN19 image generation synapse."""
    prompt: str = ""
    size: str = "1024x1024"  # Resolution
    style: str = "natural"    # Style parameter
    # Response fields (populated by miner)
    image_data: str = ""      # Base64-encoded PNG
    revised_prompt: str = ""  # Miner may revise the prompt
    required_hash_fields: list[str] = ["prompt"]
```

**NOTE:** Research the actual SN19 protocol before implementation. The fields above are based on PRD requirements and may need adjustment based on the actual subnet protocol. The developer should check the Bittensor SN19 docs or subnet repo for the exact Synapse definition.

#### Image Response Format

The response follows an OpenAI-compatible format for image generation:

```json
{
  "created": 1234567890,
  "data": [
    {
      "b64_json": "<base64-encoded-png-data>",
      "revised_prompt": "A beautiful sunset..."
    }
  ]
}
```

**Key requirements:**
- `created` is Unix timestamp
- `data` is an array (even for single images)
- Either `b64_json` or `url` is present per image, not both
- `revised_prompt` is optional (miner may include it)

#### Response Validation and Sanitization

**CRITICAL for image data:**
1. Validate that `b64_json` is legitimate base64 — decode and verify it starts with PNG magic bytes (`\x89PNG`) or valid JPEG header (`\xFF\xD8\xFF`). Reject data that fails validation → `MinerInvalidResponseError`
2. Sanitize `revised_prompt` with `self.sanitize_text()` — strip HTML tags (miner content is untrusted)
3. Do NOT attempt to decode and re-encode the full image — just validate the header bytes

#### Timeout Configuration

Image generation takes significantly longer than text (10-30s miner-side). Use `sn19_timeout_seconds=90` (separate from `dendrite_timeout_seconds=30` used for text). The PRD specifies <500ms p95 gateway overhead — this is gateway processing time only, excluding miner generation time.

#### API Endpoint Path

The endpoint is `POST /v1/images/generate` per the PRD and architecture doc (NOT `/v1/images/generations` which is OpenAI's path). We use our own path.

#### Rate Limiting

Follow the same pattern as `chat.py`:
```python
async def _rate_limit_images(api_key: ApiKeyInfo) -> None:
    key = f"images_rate:{api_key.key_id}"
    result = await check_rate_limit(
        key=key,
        limit=settings.images_rate_limit_per_minute,
        window_seconds=60,
        fallback_limit=settings.images_rate_limit_per_minute,
        log_prefix="images_rate_limit",
    )
    if result == -1:
        raise RateLimitExceededError("Image generation rate limit exceeded.")
    if result is not None and result > settings.images_rate_limit_per_minute:
        raise RateLimitExceededError("Image generation rate limit exceeded.")
```

#### Error Handling

Uses the existing `GatewayError` hierarchy — no new exception types needed:
- `MinerTimeoutError` (504): Miner didn't respond within 90s
- `MinerInvalidResponseError` (502): Miner returned invalid/unparseable image data
- `SubnetUnavailableError` (503): No SN19 miners available
- `RateLimitExceededError` (429): Rate limit exceeded
- `AuthenticationError` (401): Invalid API key

### Previous Story Intelligence (Story 1.5)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Error envelope format via `GatewayError` hierarchy + `gateway_exception_handler`
- Response validated against Pydantic schema before returning (e.g., `ImageGenerationResponse.model_validate(response_data)`)
- `nh3.clean()` for text sanitization — strip all HTML tags from miner output
- `TimeoutError` → `MinerTimeoutError` (504), other exceptions → `MinerInvalidResponseError` (502)
- `enable_bittensor=False` path: `app.state.dendrite=None`, `app.state.miner_selector=None`, empty `AdapterRegistry`
- `from_response()` takes `request_data` to echo the requested model name

**Learnings from adversarial code reviews (3 rounds, 28 issues):**
- Sanitize ALL miner-provided text fields (revised_prompt is untrusted)
- Always validate outgoing data against Pydantic schemas
- Distinguish timeout errors from other failures (different status codes)
- Test all error paths with integration tests, not just unit tests
- Use `nh3` for HTML sanitization — the project already has it as a dependency

**Git intelligence — recent patterns (last 10 commits):**
- Test count: 189 tests passing as of latest commit
- Security hardening applied: body size limits, rate limiting, input validation
- Pre-existing ruff/mypy issues in `redis.py` and `api_keys.py` — do not fix (out of scope)

### Library & Framework Requirements

| Library | Version | Why |
|---|---|---|
| `bittensor` | v10.1.0 (already installed) | `bt.Synapse`, `dendrite.forward()` |
| `fastapi` | 0.135.1 (already installed) | Route handlers, `JSONResponse` |
| `pydantic` | v2 (already installed) | Schema validation |
| `structlog` | (already installed) | Structured logging |
| `nh3` | (already installed) | HTML sanitization for revised_prompt |
| `httpx` | (dev, already installed) | Test client |

No new dependencies needed — everything is already in pyproject.toml. Base64 encoding/decoding uses Python's stdlib `base64` module.

### Project Structure Notes

**New files:**
- `gateway/schemas/images.py` — `ImageGenerationRequest`, `ImageGenerationResponse`, `ImageData`
- `gateway/subnets/sn19_image.py` — `ImageGenSynapse(bt.Synapse)`, `SN19ImageAdapter(BaseAdapter)`
- `gateway/api/images.py` — `POST /v1/images/generate` route handler

**Modified files:**
- `gateway/core/config.py` — Add `sn19_netuid`, `sn19_timeout_seconds`, `images_rate_limit_per_minute`
- `gateway/main.py` — Register SN19 subnet and adapter
- `gateway/api/router.py` — Include images router

**New test files:**
- `tests/subnets/test_sn19.py`
- `tests/api/test_images.py`
- `tests/schemas/test_image_schemas.py`

**Modified test files:**
- `tests/conftest.py` — Register subnet 19 and SN19 adapter

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/prd.md#FR10] — Image generation requests with prompt, resolution, style
- [Source: _bmad-output/planning-artifacts/prd.md#FR11] — Image response as base64 PNG or URL
- [Source: _bmad-output/planning-artifacts/prd.md#NFR2] — <500ms p95 gateway overhead for SN19
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Adapter pattern, error handling
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure] — `gateway/subnets/sn19_image.py`, `gateway/api/images.py`, `gateway/schemas/images.py`
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation-Patterns] — Naming conventions, async patterns, logging, DI
- [Source: _bmad-output/implementation-artifacts/1-5-streaming-responses-and-request-cancellation.md] — Previous story patterns, review learnings, 189 tests passing
- [Source: _bmad-output/planning-artifacts/prd.md#Rate-Limiting] — SN19: 5/min, 50/day, 500/month (free tier)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- Created `ImageGenSynapse(bt.Synapse)` with prompt, size, style request fields and image_data, revised_prompt response fields
- Implemented `SN19ImageAdapter(BaseAdapter)` — thin adapter (~90 lines) with all 4 abstract methods: `to_synapse()`, `from_response()`, `sanitize_output()`, `get_config()`
- Image data validation: decodes first 12 bytes of base64, validates PNG (`\x89PNG`) or JPEG (`\xFF\xD8\xFF`) magic bytes
- Text sanitization: `revised_prompt` stripped via `nh3.clean()` (same as SN1 pattern)
- Created Pydantic schemas: `ImageGenerationRequest`, `ImageGenerationResponse`, `ImageData` — OpenAI-compatible image generation format
- Created route handler at `POST /v1/images/generate` with auth, rate limiting, schema validation, structured logging
- Wired SN19 into app lifespan: metagraph registration, null check, adapter registry with model name `tao-sn19`
- Added `sn19_netuid=19`, `sn19_timeout_seconds=90`, `images_rate_limit_per_minute=30` to Settings
- 270 tests pass (81 new + 189 existing), zero regressions, ruff clean, mypy clean

### File List

New files:
- gateway/schemas/images.py
- gateway/subnets/sn19_image.py
- gateway/api/images.py
- tests/schemas/test_image_schemas.py
- tests/subnets/test_sn19.py
- tests/api/test_images.py

Modified files:
- gateway/core/config.py
- gateway/main.py
- gateway/api/router.py
- gateway/subnets/base.py
- tests/conftest.py

### Change Log

- 2026-03-13: Implemented Story 2.1 — SN19 image generation endpoint with ImageGenSynapse, thin adapter, Pydantic schemas, route handler, app wiring, base64 image validation, text sanitization. 270 tests passing (81 new).
- 2026-03-13: Code review round 1 (Claude Opus 4.6) — 6 issues found (1 HIGH, 3 MEDIUM, 2 LOW). All fixed: n restricted to 1, miner_uid propagation in base adapter, images_rate cleanup in tests, size enum validation, style Literal enum, dendrite network error integration test. 276 tests passing.
- 2026-03-13: Code review round 2 (Claude Opus 4.6) — 5 issues found (1 HIGH, 2 MEDIUM, 2 LOW). All fixed: removed url response_format (security), fixed exception chain context, added integration tests for size/style/format validation, added chat_rate cleanup. 278 tests passing.

## Senior Developer Review (AI)

### Round 1

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested → All Fixed

- [x] [HIGH] H1: `n` field accepted but silently ignored — restricted to `Literal[1]`
- [x] [MEDIUM] M1: `miner_uid="unknown"` in adapter errors — base adapter now re-raises with actual miner_uid
- [x] [MEDIUM] M2: Missing `images_rate:*` in test cleanup — added to `_flush_test_state()`
- [x] [MEDIUM] M3: `size` field has no format validation — added `_ALLOWED_SIZES` set + `model_validator`
- [x] [LOW] L1: `style` field has no enum validation — changed to `Literal["natural", "vivid"] | None`
- [x] [LOW] L2: Missing integration test for dendrite network error — added `test_image_generation_502_dendrite_network_error`

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 2 |
| **Total** | **6** |

### Round 2

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested → All Fixed

- [x] [HIGH] H1: `response_format="url"` bypasses all image validation — removed URL format (MVP only supports b64_json)
- [x] [MEDIUM] M1: Base adapter re-raise uses `exc.__cause__` (may be None) — changed to `from exc`
- [x] [MEDIUM] M2: Missing integration tests for size/style validation — added 3 tests (invalid size, invalid style, url format rejected)
- [x] [LOW] L1: `chat_rate:*` keys not cleaned in test fixtures — added to cleanup patterns
- [x] [LOW] L2: Duplicate `_get_api_key` helper — noted, not refactored (minor)

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 2 |
| **Total** | **5** |
