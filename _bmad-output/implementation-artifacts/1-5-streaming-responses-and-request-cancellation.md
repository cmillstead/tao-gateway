# Story 1.5: Streaming Responses & Request Cancellation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to stream text generation responses via SSE,
So that I can use `stream=True` with OpenAI client libraries and get tokens as they're generated.

## Acceptance Criteria

1. **Given** I am authenticated with a valid API key, **when** I send `POST /v1/chat/completions` with `stream: true`, **then** the gateway returns a `text/event-stream` response, **and** tokens are sent as SSE events in OpenAI-compatible `data: {...}` format, **and** the stream ends with `data: [DONE]` (FR47).

2. **Given** I am streaming a response using the OpenAI Python client, **when** I iterate over `client.chat.completions.create(stream=True)`, **then** the response parses correctly through the OpenAI client library without modification.

3. **Given** I am receiving a streaming response, **when** I disconnect (close the connection) mid-stream, **then** the gateway detects the disconnection, **and** cancels the upstream Dendrite query to the miner (FR48), **and** resources are released promptly.

4. **Given** a streaming request, **when** the miner times out or returns an error mid-stream, **then** the gateway sends an SSE error event with miner UID and error details, **and** closes the stream cleanly.

5. **Given** a streaming response, **when** response headers are sent, **then** they include `X-TaoGateway-Miner-UID` and `X-TaoGateway-Subnet`, **and** `X-TaoGateway-Latency-Ms` reflects time-to-first-token.

## Tasks / Subtasks

- [x] Task 1: Streaming Synapse definition (AC: #1, #2)
  - [x] 1.1: Create `TextGenStreamingSynapse(bt.StreamingSynapse)` in `gateway/subnets/sn1_text.py` — extends existing module. Implements abstract `process_streaming_response(response)` to yield token chunks from the miner's streaming HTTP response.
  - [x] 1.2: Implement `extract_response_json(response)` abstract method — extracts accumulated completion text from stream chunks.
  - [x] 1.3: Set `required_hash_fields = ["roles", "messages"]` matching `TextGenSynapse`.

- [x] Task 2: Base adapter streaming support (AC: #1, #3, #4, #5)
  - [x] 2.1: Add `async def execute_stream()` method to `BaseAdapter` in `gateway/subnets/base.py` — returns `AsyncGenerator[str, None]` yielding SSE-formatted `data: {...}\n\n` strings.
  - [x] 2.2: Call `dendrite.forward(axons=[axon], synapse=synapse, timeout=config.timeout_seconds, streaming=True)` — returns `AsyncGenerator` per the SDK.
  - [x] 2.3: Wrap the async generator iteration with disconnect detection — if `request.is_disconnected()` returns True, break the loop and clean up.
  - [x] 2.4: On miner timeout/error mid-stream, yield an SSE error event: `data: {"error": {"type": "...", "message": "..."}}\n\n` then close.
  - [x] 2.5: Track `time_to_first_token` — elapsed time from request start to first yielded chunk. Set `X-TaoGateway-Latency-Ms` to this value.
  - [x] 2.6: Add abstract method `to_streaming_synapse(request_data) -> bt.StreamingSynapse` for concrete adapters to implement.
  - [x] 2.7: Add abstract method `format_stream_chunk(chunk) -> str` for concrete adapters to format raw miner chunks into OpenAI SSE format.

- [x] Task 3: SN1 streaming adapter methods (AC: #1, #2)
  - [x] 3.1: Implement `to_streaming_synapse()` in `SN1TextAdapter` — creates `TextGenStreamingSynapse` with roles/messages from request.
  - [x] 3.2: Implement `format_stream_chunk(chunk)` — wraps each text chunk in OpenAI streaming delta format: `{"id": "chatcmpl-...", "object": "chat.completion.chunk", "created": N, "model": "tao-sn1", "choices": [{"index": 0, "delta": {"content": "..."}, "finish_reason": null}]}`.
  - [x] 3.3: Implement `format_stream_done()` — returns the final chunk with `finish_reason: "stop"` and empty delta, followed by `data: [DONE]`.
  - [x] 3.4: Sanitize each chunk through the dangerous-tag regex before yielding (reuse `_DANGEROUS_TAGS_RE`, `_EVENT_HANDLER_RE`, `_JS_PROTOCOL_RE`).

- [x] Task 4: Route handler streaming path (AC: #1, #2, #3, #5)
  - [x] 4.1: Update `create_chat_completion()` in `gateway/api/chat.py` — remove the 501 response for `stream=True`. Instead, call `adapter.execute_stream()` and return `StreamingResponse`.
  - [x] 4.2: Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"` and headers `Cache-Control: no-cache`, `Connection: keep-alive`.
  - [x] 4.3: Set gateway headers (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Subnet`) on the `StreamingResponse`. Note: `X-TaoGateway-Latency-Ms` must be set as first-token time, injected as an SSE comment or header before first data chunk.
  - [x] 4.4: Pass `request` object to `execute_stream()` so it can check `request.is_disconnected()` for cancellation (AC#3).
  - [x] 4.5: Log `chat_completion_stream_request` at start, `chat_completion_stream_complete` / `chat_completion_stream_error` at end with structlog.

- [x] Task 5: OpenAI streaming response schemas (AC: #2)
  - [x] 5.1: Create `ChatCompletionChunk` Pydantic model in `gateway/schemas/chat.py` — matching OpenAI's streaming chunk format: `id`, `object` (literal `"chat.completion.chunk"`), `created`, `model`, `choices` (list of `ChunkChoice` with `index`, `delta` (`DeltaMessage`), `finish_reason`).
  - [x] 5.2: Create `DeltaMessage` model: `role` (optional str), `content` (optional str) — only the changing fields.
  - [x] 5.3: Create `ChunkChoice` model: `index` (int), `delta` (DeltaMessage), `finish_reason` (optional str).

- [x] Task 6: Tests (AC: all)
  - [x] 6.1: Create `tests/subnets/test_sn1_streaming.py` — test `TextGenStreamingSynapse` creation, `to_streaming_synapse()` conversion, `format_stream_chunk()` output matches OpenAI format, `format_stream_done()` ends with `[DONE]`, chunk sanitization strips dangerous content.
  - [x] 6.2: Create `tests/subnets/test_base_adapter_streaming.py` — test `execute_stream()` flow: yields SSE chunks, sends `[DONE]` at end, handles miner timeout mid-stream, handles empty stream, tracks time-to-first-token.
  - [x] 6.3: Update `tests/api/test_chat.py` — integration tests: successful stream (mock dendrite streaming returns chunks), verify `text/event-stream` content type, verify `data: [DONE]` terminator, verify SSE error event on miner timeout, verify response headers present, verify 422 still works for malformed requests with `stream=true`, verify client disconnect cancels upstream (mock `request.is_disconnected()`).
  - [x] 6.4: Add streaming schema tests to `tests/schemas/test_chat_schemas.py` — `ChatCompletionChunk` validation, `DeltaMessage` with partial fields, serialization matches OpenAI format.
  - [x] 6.5: Verify `uv run pytest` passes with all new + existing tests.
  - [x] 6.6: Verify `uv run ruff check gateway/ tests/` and `uv run mypy gateway/` pass with zero errors on new code.

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Bittensor SDK Streaming API

The Bittensor SDK v10.1.0 `dendrite.forward()` supports streaming natively:

```python
# Streaming call — returns list of AsyncGenerators (one per axon)
responses = await dendrite.forward(
    axons=[axon],
    synapse=streaming_synapse,
    timeout=config.timeout_seconds,
    streaming=True,  # KEY: enables streaming mode
)
# responses[0] is an AsyncGenerator[Any, Any] — yields chunks
async for chunk in responses[0]:
    # chunk is raw text/bytes from the miner
    process(chunk)
```

**CRITICAL:** When `streaming=True`, the synapse MUST extend `bt.StreamingSynapse` (not `bt.Synapse`). The SDK requires two abstract methods:
- `process_streaming_response(response)` — async generator that yields chunks from the HTTP response
- `extract_response_json(response)` — extracts response metadata from the stream

#### OpenAI Streaming Format

Each SSE event MUST follow this exact format for OpenAI client compatibility:

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"tao-sn1","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"tao-sn1","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"tao-sn1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

**Key requirements:**
- Each `data:` line followed by two newlines (`\n\n`)
- `id` is consistent across all chunks in one stream
- First chunk MAY include `delta.role: "assistant"` (OpenAI convention)
- Last content chunk has `finish_reason: "stop"` and empty `delta`
- Stream terminates with `data: [DONE]\n\n`
- `object` is `"chat.completion.chunk"` (NOT `"chat.completion"`)

#### Client Disconnect Detection (FR48)

FastAPI provides `request.is_disconnected()` for ASGI disconnect detection:

```python
from starlette.requests import Request

async def stream_generator(request: Request):
    async for chunk in miner_stream:
        if await request.is_disconnected():
            # Client disconnected — cancel upstream
            break
        yield f"data: {chunk}\n\n"
```

**CRITICAL:** The generator must be wrapped in a try/finally to ensure cleanup even on disconnect. Use `asyncio.CancelledError` handling if the task is cancelled.

#### StreamingResponse Pattern

```python
from fastapi.responses import StreamingResponse

return StreamingResponse(
    stream_generator(request, ...),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-TaoGateway-Miner-UID": miner_uid,
        "X-TaoGateway-Subnet": config.subnet_name,
    },
)
```

**Note:** `X-TaoGateway-Latency-Ms` cannot be set as a response header for streaming because headers are sent before the first chunk. Instead, either:
1. Include it as an SSE comment before the first data event: `: latency_ms=42\n\n`
2. Include it in the first SSE data chunk as a custom field

Option 1 is preferred — SSE comments (lines starting with `:`) are ignored by OpenAI clients.

#### Error Handling in Streams

Errors mid-stream cannot use HTTP status codes (headers already sent as 200). Instead:

```python
# SSE error event format
yield f'data: {{"error": {{"type": "gateway_timeout", "message": "Miner timed out", "miner_uid": "{miner_uid}"}}}}\n\n'
yield "data: [DONE]\n\n"
```

#### Fat Base / Thin Adapter — Streaming Extension

The streaming methods follow the same pattern as non-streaming:
- **Base adapter** handles: miner selection, dendrite streaming call, disconnect detection, error handling, header injection, latency tracking
- **Concrete adapter** provides: `to_streaming_synapse()`, `format_stream_chunk()`, `format_stream_done()`, config

The concrete adapter's streaming methods should be ~20-30 lines — just format conversion.

### Previous Story Intelligence (Story 1.4)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Error envelope format via `GatewayError` hierarchy + `gateway_exception_handler`
- `ChatCompletionResponse.model_validate(response_data)` validates non-streaming responses before returning
- Targeted HTML sanitization in `sanitize_output()` — strip dangerous tags, preserve safe content
- `TimeoutError` → `MinerTimeoutError` (504), other exceptions → `MinerInvalidResponseError` (502)
- `enable_bittensor=False` path: `app.state.dendrite=None`, `app.state.miner_selector=None`, empty `AdapterRegistry`
- All `GatewayError` and unexpected exceptions logged with `chat_completion_error` event
- `from_response()` takes `request_data` to echo the requested model name
- `model` field has `min_length=1`, `max_tokens` has `ge=1`

**Learnings from adversarial code reviews (3 rounds on Story 1.4, 23 issues total):**
- Sanitize every chunk, not just the final response — miner content is untrusted
- Don't strip all HTML — use targeted dangerous-tag regex to preserve legitimate code/math content
- Always validate outgoing data against Pydantic schemas
- Set defensive defaults on app.state for Bittensor-disabled path
- Distinguish timeout errors from other failures (different status codes)
- Test all error paths with integration tests, not just unit tests

**Git intelligence — recent patterns (last 15 commits):**
- Test count: 164 tests passing as of latest commit
- Sanitization: targeted dangerous-tag stripping with javascript: protocol coverage
- Response validation: `ChatCompletionResponse.model_validate()` before returning
- Error classification: `TimeoutError` → 504, other exceptions → 502
- Pre-existing ruff/mypy issues in `redis.py` and `api_keys.py` — do not fix (out of scope)

### Library & Framework Requirements

| Library | Version | Why |
|---|---|---|
| `bittensor` | v10.1.0 (already installed) | `StreamingSynapse`, `dendrite.forward(streaming=True)` |
| `fastapi` | 0.135.1 (already installed) | `StreamingResponse`, SSE support |
| `pydantic` | v2 (already installed) | `ChatCompletionChunk` schema |
| `structlog` | (already installed) | Structured logging |
| `httpx` | (dev, already installed) | Test client — supports streaming responses via `stream()` |

No new dependencies needed — everything is already in pyproject.toml.

**Bittensor SDK v10.1.0 streaming specifics:**
- `bt.StreamingSynapse` extends `bt.Synapse` + ABC
- `dendrite.forward(streaming=True)` returns `list[AsyncGenerator]`
- Must implement `process_streaming_response(response)` and `extract_response_json(response)`
- `required_hash_fields` works the same as non-streaming Synapse

### Project Structure Notes

Modified files:
- `gateway/subnets/sn1_text.py` — add `TextGenStreamingSynapse`, streaming methods on `SN1TextAdapter`
- `gateway/subnets/base.py` — add `execute_stream()`, `to_streaming_synapse()`, `format_stream_chunk()` abstract methods
- `gateway/api/chat.py` — replace 501 with streaming path, use `StreamingResponse`
- `gateway/schemas/chat.py` — add `ChatCompletionChunk`, `DeltaMessage`, `ChunkChoice`

New test files:
- `tests/subnets/test_sn1_streaming.py`
- `tests/subnets/test_base_adapter_streaming.py`

Modified test files:
- `tests/api/test_chat.py` — streaming integration tests
- `tests/schemas/test_chat_schemas.py` — chunk schema tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.5] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/prd.md#FR47] — Streaming SSE for SN1 chat completions
- [Source: _bmad-output/planning-artifacts/prd.md#FR48] — Cancel upstream on client disconnect
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Adapter pattern, error handling
- [Source: _bmad-output/planning-artifacts/architecture.md#Deferred-Decisions] — Streaming listed as Phase 2 but included in Epic 1 stories
- [Source: _bmad-output/implementation-artifacts/1-4-sn1-text-generation-endpoint.md] — Previous story patterns, SDK usage, sanitization approach, review learnings
- [Source: Bittensor SDK v10.1.0 — StreamingSynapse class] — `process_streaming_response()`, `extract_response_json()` abstract methods
- [Source: Bittensor SDK v10.1.0 — dendrite.forward()] — `streaming=True` parameter, returns `list[AsyncGenerator]`
- [Source: OpenAI API reference — Chat Completions Streaming] — SSE chunk format, `chat.completion.chunk` object type, `[DONE]` terminator

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- Implemented `TextGenStreamingSynapse(bt.StreamingSynapse)` with `process_streaming_response()` and `extract_response_json()` abstract methods
- Added `execute_stream()` to `BaseAdapter` — handles miner selection, dendrite streaming call, disconnect detection, error handling, TTFT tracking
- `SN1TextAdapter` streaming methods: `to_streaming_synapse()`, `format_stream_chunk()`, `format_stream_done()`, `sanitize_text()` — all reuse existing sanitization regexes
- Updated chat route handler: replaced 501 for `stream=True` with full `StreamingResponse` path using `text/event-stream` media type
- Added `ChatCompletionChunk`, `DeltaMessage`, `ChunkChoice` Pydantic schemas matching OpenAI streaming format
- Gateway headers (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Subnet`) set on StreamingResponse; TTFT sent as SSE comment (`: ttft_ms=N`)
- Client disconnect detection via `request.is_disconnected()` — breaks streaming loop on disconnect (FR48)
- Mid-stream errors sent as SSE error events with miner UID, followed by `data: [DONE]`
- 189 tests pass (25 new + 164 existing), zero regressions
- Ruff clean on all new code, mypy clean on all new code (1 pre-existing error in api_keys.py)

### File List

Modified files:
- gateway/schemas/chat.py (added ChatCompletionChunk, DeltaMessage, ChunkChoice)
- gateway/subnets/sn1_text.py (added TextGenStreamingSynapse, streaming adapter methods, sanitize_text)
- gateway/subnets/base.py (added execute_stream, streaming abstract methods, _sse_error)
- gateway/api/chat.py (replaced 501 with streaming path, refactored into _handle_stream/_handle_non_stream)

New test files:
- tests/subnets/test_sn1_streaming.py
- tests/subnets/test_base_adapter_streaming.py

Modified test files:
- tests/api/test_chat.py (replaced 501 test with streaming success/error/422/503 tests)
- tests/schemas/test_chat_schemas.py (added chunk schema tests)

### Change Log

- 2026-03-13: Implemented Story 1.5 — SSE streaming responses with OpenAI-compatible chat.completion.chunk format, client disconnect cancellation, mid-stream error handling, TTFT tracking. 189 tests passing (25 new).
- 2026-03-13: Code review round 1 (Claude Opus 4.6) — 7 issues found (1 HIGH, 3 MEDIUM, 3 LOW). All fixed: single miner selection, stop chunk only on success, try/finally cleanup, first-chunk role, module-level json import, stream_complete log fix. 189 tests passing.

## Senior Developer Review (AI)

### Round 1

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested → All Fixed

- [x] [HIGH] H1: Double miner selection — now selected once in `_handle_stream()` and passed to `execute_stream()`
- [x] [MEDIUM] M1: Stop chunk no longer sent after mid-stream errors — only `[DONE]` terminator
- [x] [MEDIUM] M2: `try/finally` added for stream cleanup logging on disconnect
- [x] [MEDIUM] M3: First chunk includes `delta.role: "assistant"` per OpenAI convention
- [x] [LOW] L1: `json` imported at module level in `base.py`
- [x] [LOW] L2: `chat_completion_stream_complete` log only emitted on success
- [x] [LOW] L3: Accepted — `ChatCompletionChunk` schema for documentation/testing (consistent with non-streaming)

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 3 |
| **Total** | **7** |
