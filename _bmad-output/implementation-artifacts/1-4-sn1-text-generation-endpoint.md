# Story 1.4: SN1 Text Generation Endpoint

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to send text generation requests to an OpenAI-compatible endpoint,
So that I can use decentralized AI by swapping `base_url` in my existing OpenAI client code.

## Acceptance Criteria

1. **Given** I am authenticated with a valid API key, **when** I send `POST /v1/chat/completions` with an OpenAI-compatible request body (model, messages array), **then** the gateway translates my request into a TextGenSynapse, **and** routes it to a selected miner via Dendrite, **and** returns an OpenAI ChatCompletion-formatted JSON response.

2. **Given** the SN1 adapter processes a miner response, **when** the response is returned, **then** it passes through `openai.ChatCompletion` client parsing unchanged (NFR26), **and** response headers include `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`.

3. **Given** I send a malformed request body, **when** Pydantic validation fails, **then** I receive a 422 response with field-level validation errors (FR26), **and** the error follows the standard error envelope format.

4. **Given** a miner returns an invalid or potentially malicious response, **when** the adapter processes the response, **then** the output is sanitized against the expected schema before returning to me (FR35, NFR12).

5. **Given** the selected miner times out, **when** the Dendrite query exceeds the timeout threshold, **then** I receive a 504 response with the miner UID in the error metadata, **and** the error distinguishes this as an upstream failure, not a gateway error (FR24).

6. **Given** all SN1 miners are unavailable, **when** the miner selector finds no eligible miners, **then** I receive a 503 response with a clear message about subnet unavailability (NFR23), **and** other subnet endpoints remain unaffected.

7. **Given** the base adapter class, **when** a new subnet adapter is needed in the future, **then** the fat-base/thin-adapter pattern is established: base handles miner selection, Dendrite query, response validation, sanitization; concrete adapter provides `to_synapse()`, `from_response()`, and config (~50 lines).

8. **Given** normal request handling, **when** measuring gateway-added latency (excluding miner response time), **then** p95 overhead is under 200ms (NFR1).

## Tasks / Subtasks

- [x] Task 1: OpenAI-compatible Pydantic schemas (AC: #1, #2, #3)
  - [x] 1.1: Create `gateway/schemas/chat.py` — `ChatCompletionRequest` schema matching OpenAI's `POST /v1/chat/completions` request format: `model` (str), `messages` (list of `ChatMessage` with `role`/`content`), `temperature` (optional float 0-2), `max_tokens` (optional int), `top_p` (optional float), `stream` (bool, default false — validate but reject with 501 until Story 1.5)
  - [x] 1.2: Create `ChatCompletionResponse` schema matching OpenAI format: `id` (str, `chatcmpl-{uuid}`), `object` (literal `"chat.completion"`), `created` (int, unix timestamp), `model` (str), `choices` (list of `Choice` with `index`, `message` (`ChatMessage`), `finish_reason`), `usage` (`CompletionUsage` with `prompt_tokens`, `completion_tokens`, `total_tokens`)
  - [x] 1.3: Create `ChatMessage` schema: `role` (literal `"system"` | `"user"` | `"assistant"`), `content` (str)
  - [x] 1.4: Validate: `messages` must be non-empty, at least one `user` message required

- [x] Task 2: TextGenSynapse protocol definition (AC: #1, #4)
  - [x] 2.1: Create `gateway/subnets/sn1_text.py` — define `TextGenSynapse(bt.Synapse)` with fields: `roles` (list[str]), `messages` (list[str]), `completion` (str, output field, default "")
  - [x] 2.2: Set `required_hash_fields = ["roles", "messages"]` for request integrity
  - [x] 2.3: Document that SN1 miners expect role/message parallel arrays and return completion as plain text

- [x] Task 3: Base subnet adapter (AC: #7)
  - [x] 3.1: Create `gateway/subnets/base.py` — `BaseAdapter` ABC with methods: `to_synapse(request) -> bt.Synapse`, `from_response(synapse) -> dict`, `sanitize_output(response_data) -> dict`, `get_config() -> AdapterConfig`
  - [x] 3.2: Implement shared logic in base: miner selection via `MinerSelector`, Dendrite query via `dendrite.forward()`, response validation, output sanitization, gateway header injection, latency measurement
  - [x] 3.3: Define `AdapterConfig` dataclass: `netuid` (int), `subnet_name` (str), `timeout_seconds` (int), `max_retries` (int, default 0 for MVP)
  - [x] 3.4: Base adapter `execute()` method orchestrates the full flow: `to_synapse` → select miner → dendrite query → validate response → `from_response` → `sanitize_output` → return with headers
  - [x] 3.5: Handle Dendrite errors: timeout → `MinerTimeoutError`, invalid response → `MinerInvalidResponseError`, no miners → `SubnetUnavailableError`

- [x] Task 4: SN1 concrete adapter (~50 lines) (AC: #1, #2, #4)
  - [x] 4.1: Implement `SN1TextAdapter(BaseAdapter)` in `gateway/subnets/sn1_text.py`
  - [x] 4.2: `to_synapse()`: Convert `ChatCompletionRequest` → `TextGenSynapse` — extract roles and messages from request messages array into parallel lists
  - [x] 4.3: `from_response()`: Convert `TextGenSynapse.completion` (plain text) → `ChatCompletionResponse` — wrap in OpenAI-compatible response format with generated `id`, `created` timestamp, proper `choices` structure
  - [x] 4.4: `sanitize_output()`: Validate response is valid JSON/string, strip any suspicious HTML/script tags from completion text, ensure response passes OpenAI client parsing
  - [x] 4.5: `get_config()`: Return `AdapterConfig(netuid=settings.sn1_netuid, subnet_name="sn1", timeout_seconds=settings.dendrite_timeout_seconds)`

- [x] Task 5: Adapter registry (AC: #7)
  - [x] 5.1: Create `gateway/subnets/registry.py` — `AdapterRegistry` class mapping netuid → adapter instance
  - [x] 5.2: Implement `register(adapter)`, `get(netuid) -> BaseAdapter`, `get_by_model(model_name) -> BaseAdapter`
  - [x] 5.3: Register SN1 adapter during lifespan startup, store in `app.state.adapter_registry`

- [x] Task 6: Chat completions route handler (AC: #1, #2, #3, #5, #6, #8)
  - [x] 6.1: Create `gateway/api/chat.py` — `POST /v1/chat/completions` endpoint
  - [x] 6.2: Require API key auth via `Depends(get_current_api_key)` — returns `ApiKeyInfo`
  - [x] 6.3: Validate request body with `ChatCompletionRequest` schema (Pydantic auto-returns 422)
  - [x] 6.4: If `stream=True`, return 501 Not Implemented (deferred to Story 1.5)
  - [x] 6.5: Get SN1 adapter from `request.app.state.adapter_registry`
  - [x] 6.6: Call `adapter.execute(request_data, dendrite, miner_selector)` — returns response dict + gateway headers
  - [x] 6.7: Return `JSONResponse` with response body and custom headers: `X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`
  - [x] 6.8: Log request lifecycle: `chat_completion_request` (start), `chat_completion_success` / `chat_completion_error` (end) with structlog

- [x] Task 7: Router integration (AC: #1)
  - [x] 7.1: Update `gateway/api/router.py` — include chat router with `prefix="/v1"`, `tags=["Chat Completions"]`
  - [x] 7.2: Update `gateway/main.py` lifespan — initialize `AdapterRegistry`, register SN1 adapter, store in `app.state`

- [x] Task 8: Tests (AC: all)
  - [x] 8.1: Create `tests/subnets/test_sn1.py` — test `to_synapse()` conversion (messages → roles/messages arrays), `from_response()` conversion (completion → OpenAI format), `sanitize_output()` (strips dangerous content), invalid miner response handling
  - [x] 8.2: Create `tests/subnets/test_base_adapter.py` — test `execute()` flow: miner selection, dendrite call, response processing; test error paths: timeout, invalid response, no miners
  - [x] 8.3: Create `tests/api/test_chat.py` — integration tests: successful completion (mock dendrite returns valid synapse), 422 on malformed request (empty messages, missing model), 504 on miner timeout, 502 on invalid miner response, 503 on subnet unavailable, 501 on stream=true, verify response headers present, verify response passes OpenAI schema validation
  - [x] 8.4: Create `tests/subnets/__init__.py`
  - [x] 8.5: Add shared fixtures to `tests/conftest.py` — mock dendrite that returns configurable synapse responses, mock adapter registry
  - [x] 8.6: Verify `uv run pytest` passes with all new + existing tests
  - [x] 8.7: Verify `uv run ruff check gateway/ tests/` and `uv run mypy gateway/` pass with zero errors on new code

### Review Follow-ups (AI)

- [x] [AI-Review][HIGH] H1: Expand `sanitize_output()` beyond `<script>` tags — strip all HTML tags for full XSS protection (AC#4, FR35)
- [x] [AI-Review][HIGH] H2: `enable_bittensor=False` path in lifespan now sets empty `AdapterRegistry` — graceful 503 instead of crash
- [x] [AI-Review][HIGH] H3: Added `chat_completion_error` log when `adapter.execute()` raises `GatewayError`
- [x] [AI-Review][MEDIUM] M1: `from_response()` now echoes requested model name via `request_data` parameter
- [x] [AI-Review][MEDIUM] M2: Empty `dendrite.forward()` response now raises `MinerInvalidResponseError` (not misdiagnosed as timeout)
- [x] [AI-Review][MEDIUM] M3: `_clean_state` fixture now resets `app.state.miner_selector`, `dendrite`, `adapter_registry`
- [x] [AI-Review][MEDIUM] M4: `max_tokens` now has `ge=1` constraint
- [x] [AI-Review][LOW] L1: Removed unused `structlog` logger from `sn1_text.py`
- [x] [AI-Review][LOW] L2: Added `test_app` fixture; tests use it instead of `client._transport.app`

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Fat Base / Thin Adapter Pattern

```python
# gateway/subnets/base.py
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import bittensor as bt
import structlog

from gateway.core.exceptions import (
    MinerInvalidResponseError,
    MinerTimeoutError,
    SubnetUnavailableError,
)
from gateway.routing.selector import MinerSelector

logger = structlog.get_logger()

@dataclass
class AdapterConfig:
    netuid: int
    subnet_name: str
    timeout_seconds: int
    max_retries: int = 0  # MVP: no retries

class BaseAdapter(ABC):
    """Fat base class — handles miner selection, Dendrite query, response
    validation, sanitization. Concrete adapters provide only ~50 lines:
    to_synapse(), from_response(), sanitize_output(), get_config()."""

    @abstractmethod
    def to_synapse(self, request_data: dict) -> bt.Synapse:
        """Convert API request to subnet-specific Synapse."""
        ...

    @abstractmethod
    def from_response(self, synapse: bt.Synapse) -> dict:
        """Convert miner's Synapse response to API response dict."""
        ...

    @abstractmethod
    def sanitize_output(self, response_data: dict) -> dict:
        """Sanitize miner response before returning to consumer."""
        ...

    @abstractmethod
    def get_config(self) -> AdapterConfig:
        """Return adapter configuration."""
        ...

    async def execute(
        self,
        request_data: dict,
        dendrite: bt.Dendrite,
        miner_selector: MinerSelector,
    ) -> tuple[dict, dict]:
        """Full request lifecycle. Returns (response_body, gateway_headers)."""
        config = self.get_config()
        start_time = time.monotonic()

        # 1. Select miner (raises SubnetUnavailableError if none)
        axon = miner_selector.select_miner(config.netuid)
        miner_uid = axon.hotkey[:8]  # Safe prefix for logging/headers

        # 2. Build synapse
        synapse = self.to_synapse(request_data)

        # 3. Query miner via Dendrite
        try:
            responses = await dendrite.forward(
                axons=[axon],
                synapse=synapse,
                timeout=config.timeout_seconds,
            )
            response_synapse = responses[0]
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "dendrite_query_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                elapsed_ms=round(elapsed * 1000),
            )
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc

        # 4. Validate response
        if response_synapse.is_timeout:
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        if not response_synapse.is_success:
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )

        # 5. Convert and sanitize
        response_data = self.from_response(response_synapse)
        response_data = self.sanitize_output(response_data)

        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 6. Gateway headers
        headers = {
            "X-TaoGateway-Miner-UID": miner_uid,
            "X-TaoGateway-Latency-Ms": str(elapsed_ms),
            "X-TaoGateway-Subnet": config.subnet_name,
        }

        return response_data, headers
```

**CRITICAL:** `dendrite.forward()` is the async method for querying miners. It returns a list of synapse responses (one per axon). Check `response_synapse.is_success` and `response_synapse.is_timeout` to determine outcome.

#### SN1 Adapter Pattern

```python
# gateway/subnets/sn1_text.py
import time
import uuid
import re

import bittensor as bt
import structlog

from gateway.core.config import settings
from gateway.subnets.base import AdapterConfig, BaseAdapter

logger = structlog.get_logger()

class TextGenSynapse(bt.Synapse):
    """SN1 text generation synapse. Miners expect parallel role/message arrays."""
    roles: list[str] = []
    messages: list[str] = []
    completion: str = ""
    required_hash_fields: list[str] = ["roles", "messages"]

class SN1TextAdapter(BaseAdapter):
    """Thin adapter: OpenAI chat format ↔ TextGenSynapse."""

    def to_synapse(self, request_data: dict) -> TextGenSynapse:
        messages = request_data["messages"]
        return TextGenSynapse(
            roles=[m["role"] for m in messages],
            messages=[m["content"] for m in messages],
        )

    def from_response(self, synapse: TextGenSynapse) -> dict:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "tao-sn1",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": synapse.completion,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,  # Bittensor doesn't report token counts
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    def sanitize_output(self, response_data: dict) -> dict:
        # Sanitize completion text — strip script tags, null bytes
        content = response_data["choices"][0]["message"]["content"]
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = content.replace("\x00", "")
        response_data["choices"][0]["message"]["content"] = content
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn1_netuid,
            subnet_name="sn1",
            timeout_seconds=settings.dendrite_timeout_seconds,
        )
```

**CRITICAL:** The Bittensor SDK uses Pydantic v2 internally for Synapse models. Our `TextGenSynapse` extends `bt.Synapse`. The `required_hash_fields` ensures request integrity. Never import or inherit from SDK Synapse models in our schema layer — `gateway/schemas/chat.py` must be pure Pydantic, independent of the SDK.

#### OpenAI-Compatible Response Format

The response MUST pass through `openai.ChatCompletion` client parsing unchanged. Key requirements:
- `id`: string starting with `chatcmpl-`
- `object`: exactly `"chat.completion"`
- `created`: Unix timestamp (int)
- `model`: string (we use `"tao-sn1"`)
- `choices`: array with at least one choice containing `message.role`, `message.content`, `finish_reason`
- `usage`: object with `prompt_tokens`, `completion_tokens`, `total_tokens` (ints)

#### Route Handler Pattern

```python
# gateway/api/chat.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
import structlog

from gateway.middleware.auth import ApiKeyInfo, get_current_api_key
from gateway.schemas.chat import ChatCompletionRequest

logger = structlog.get_logger()
router = APIRouter()

@router.post("/chat/completions")
async def create_chat_completion(
    body: ChatCompletionRequest,
    request: Request,
    api_key: ApiKeyInfo = Depends(get_current_api_key),
) -> JSONResponse:
    if body.stream:
        # Streaming deferred to Story 1.5
        return JSONResponse(
            status_code=501,
            content={"error": {"type": "not_implemented", "message": "Streaming not yet supported. Use stream=false.", "code": 501}},
        )

    adapter = request.app.state.adapter_registry.get_by_model(body.model)
    dendrite = request.app.state.dendrite
    miner_selector = request.app.state.miner_selector

    logger.info("chat_completion_request", model=body.model, message_count=len(body.messages))

    response_data, headers = await adapter.execute(
        request_data=body.model_dump(),
        dendrite=dendrite,
        miner_selector=miner_selector,
    )

    return JSONResponse(content=response_data, headers=headers)
```

**CRITICAL patterns from previous stories:**
- Use `Depends(get_current_api_key)` for API key auth — returns `ApiKeyInfo` with `key_id` and `org_id`
- Use `request.app.state` for singletons (dendrite, miner_selector, adapter_registry)
- Use `structlog` for all logging — never `print()` or stdlib `logging`
- Errors handled by `gateway_exception_handler` automatically — `MinerTimeoutError` → 504, `MinerInvalidResponseError` → 502, `SubnetUnavailableError` → 503

#### Error Response Format

All errors use the standard envelope (already handled by `gateway_exception_handler`):
```json
{
  "error": {
    "type": "miner_timeout",
    "message": "Miner timed out on sn1",
    "code": 504,
    "subnet": "sn1",
    "miner_uid": "abc12345"
  }
}
```

#### Adapter Registry Pattern

```python
# gateway/subnets/registry.py
import structlog
from gateway.subnets.base import BaseAdapter

logger = structlog.get_logger()

class AdapterRegistry:
    """Maps netuids and model names to adapter instances."""

    def __init__(self) -> None:
        self._by_netuid: dict[int, BaseAdapter] = {}
        self._by_model: dict[str, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter, model_names: list[str] | None = None) -> None:
        config = adapter.get_config()
        self._by_netuid[config.netuid] = adapter
        if model_names:
            for name in model_names:
                self._by_model[name] = adapter
        logger.info("adapter_registered", subnet=config.subnet_name, netuid=config.netuid)

    def get(self, netuid: int) -> BaseAdapter:
        adapter = self._by_netuid.get(netuid)
        if adapter is None:
            from gateway.core.exceptions import SubnetUnavailableError
            raise SubnetUnavailableError(f"sn{netuid}")
        return adapter

    def get_by_model(self, model_name: str) -> BaseAdapter:
        adapter = self._by_model.get(model_name)
        if adapter is None:
            from gateway.core.exceptions import SubnetUnavailableError
            raise SubnetUnavailableError(model_name)
        return adapter
```

#### Test Strategy

**Mocking approach — same as Story 1.3:**
- Mock `bt.Dendrite.forward()` to return controllable synapse responses
- Mock `MinerSelector.select_miner()` to return a known `AxonInfo`
- Use real Pydantic validation for schema tests
- Use `httpx.AsyncClient` with `ASGITransport` for integration tests

**Key test fixtures needed:**
```python
@pytest.fixture
def mock_successful_synapse():
    """TextGenSynapse with valid completion."""
    synapse = MagicMock()
    synapse.completion = "Hello! I'm a decentralized AI assistant."
    synapse.is_success = True
    synapse.is_timeout = False
    return synapse

@pytest.fixture
def mock_timeout_synapse():
    """TextGenSynapse that timed out."""
    synapse = MagicMock()
    synapse.is_success = False
    synapse.is_timeout = True
    return synapse
```

**Integration test pattern:**
```python
@pytest.mark.asyncio
async def test_chat_completion_success(client, auth_headers):
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "tao-sn1", "messages": [{"role": "user", "content": "Hello"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "X-TaoGateway-Miner-UID" in response.headers
```

### Previous Story Intelligence (Story 1.3)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Error envelope format via `GatewayError` hierarchy + `gateway_exception_handler`
- Redis circuit breaker pattern in `gateway/core/redis.py`
- Health endpoint with in-memory cache (5s TTL)
- `ruff check` + `mypy` must pass with zero errors
- Use `from __future__ import annotations` pattern sparingly
- Type ignore comments need justification
- Pre-existing ruff/mypy issues in `redis.py` and `api_keys.py` — do not fix (out of scope)

**Learnings from adversarial code reviews (10 rounds on Story 1.3):**
- Run `subtensor.metagraph()` in executor — blocking I/O (already done in 1.3)
- Never log sensitive data (wallet keys, full API keys)
- Health endpoint already has cache — extend it, don't create parallel caching
- Bittensor init is now conditional via `ENABLE_BITTENSOR` setting — adapter tests should work even when Bittensor is disabled (mock everything)
- `dendrite.forward()` is async — use `await` directly, no executor needed
- Shutdown must close dendrite session properly (`await dendrite.aclose_session()`)
- Use `sync_generation` for cache invalidation (already implemented in MetagraphManager)
- ThreadPoolExecutor is dedicated for metagraph sync — don't reuse for other blocking calls

**Git intelligence — recent patterns (last 15 commits):**
- Test count: 103 tests passing as of latest commit
- Rate limiting: uses registered Lua script (`ed5c5e0`)
- Security: blocks known-weak JWT secrets in production (`2de0b70`)
- Bittensor: conditional init via `enable_bittensor` setting (`24fd890`)
- Health: degrades gracefully when Redis unreachable (`d21c023`)

### Library & Framework Requirements

| Library | Version | Why |
|---|---|---|
| `bittensor` | v10.1.0 (already installed) | Synapse base class, Dendrite for miner queries |
| `fastapi` | (already installed) | Route handlers, dependency injection, JSONResponse |
| `pydantic` | v2 (already installed) | Request/response schema validation |
| `structlog` | (already installed) | Structured logging |
| `httpx` | (dev, already installed) | Test client for integration tests |

No new dependencies needed — everything is already in pyproject.toml.

**Bittensor SDK v10+ specifics:**
- `bt.Synapse` is a Pydantic v2 BaseModel subclass — fields are validated
- `dendrite.forward(axons=[axon], synapse=synapse, timeout=N)` — async, returns list of synapses
- Response synapse has `.is_success`, `.is_timeout`, `.axon.status_code` properties
- `required_hash_fields` — list of field names included in request hash for integrity

### Project Structure Notes

New files to create:
```
gateway/
├── subnets/
│   ├── base.py                    # BaseAdapter ABC + AdapterConfig (fat base)
│   ├── sn1_text.py                # TextGenSynapse + SN1TextAdapter (thin adapter)
│   └── registry.py                # AdapterRegistry: netuid/model → adapter
├── api/
│   └── chat.py                    # POST /v1/chat/completions route
└── schemas/
    └── chat.py                    # ChatCompletionRequest/Response + ChatMessage

tests/
├── subnets/
│   ├── __init__.py
│   ├── test_base_adapter.py       # BaseAdapter.execute() flow + error paths
│   └── test_sn1.py                # SN1 to_synapse/from_response/sanitize tests
└── api/
    └── test_chat.py               # Integration tests for /v1/chat/completions
```

Modified files:
- `gateway/api/router.py` — add chat router include
- `gateway/main.py` — lifespan: create adapter registry, register SN1, store in app.state
- `tests/conftest.py` — add mock dendrite forward fixture, mock adapter registry fixture

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.4] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/architecture.md#Core-Architectural-Decisions] — Fat base/thin adapter pattern, adapter ~50 lines
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Error handling, rate limiting, adapter pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation-Patterns-&-Consistency-Rules] — Naming, async patterns, DI, logging
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure-&-Boundaries] — File locations: subnets/base.py, subnets/sn1_text.py, api/chat.py, schemas/chat.py
- [Source: _bmad-output/planning-artifacts/prd.md#FR8] — Text generation via OpenAI-compatible chat completions
- [Source: _bmad-output/planning-artifacts/prd.md#FR9] — Response works with existing OpenAI client libraries unchanged
- [Source: _bmad-output/planning-artifacts/prd.md#FR24] — Distinct error codes for gateway vs. upstream miner failures
- [Source: _bmad-output/planning-artifacts/prd.md#FR25] — Miner identifier and latency metadata in response headers
- [Source: _bmad-output/planning-artifacts/prd.md#FR26] — Field-level validation errors for malformed requests
- [Source: _bmad-output/planning-artifacts/prd.md#FR35] — Sanitize miner response content before returning to developer
- [Source: _bmad-output/planning-artifacts/prd.md#Performance] — <200ms p95 gateway overhead for SN1
- [Source: _bmad-output/planning-artifacts/prd.md#Security] — Output sanitization, miner responses untrusted
- [Source: _bmad-output/implementation-artifacts/1-3-bittensor-integration-and-miner-selection.md] — Previous story patterns, SDK usage, test strategy, code review learnings
- [Source: docs.bittensor.com/python-api — Synapse class] — bt.Synapse base class, dendrite.forward() signature, response properties
- [Source: OpenAI API reference — Chat Completions] — Response format that must be matched exactly

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- Implemented fat-base/thin-adapter pattern exactly as specified in architecture
- SN1TextAdapter is ~50 lines (thin adapter), BaseAdapter handles all orchestration
- OpenAI-compatible response format verified via integration tests
- Updated `MinerTimeoutError`/`MinerInvalidResponseError` miner_uid param from `int` to `str` (hotkey prefix)
- Extended `gateway_exception_handler` to include `miner_uid` and `subnet` in error responses (AC#5)
- All 148 tests pass (45 new + 103 existing), zero regressions
- Ruff clean on all new code, mypy clean on all new code (1 pre-existing error in api_keys.py)
- `tests/subnets/__init__.py` already existed from project scaffold

### File List

New files:
- gateway/schemas/chat.py
- gateway/subnets/base.py
- gateway/subnets/sn1_text.py
- gateway/subnets/registry.py
- gateway/api/chat.py
- tests/schemas/__init__.py
- tests/schemas/test_chat_schemas.py
- tests/subnets/test_sn1.py
- tests/subnets/test_base_adapter.py
- tests/subnets/test_registry.py
- tests/api/test_chat.py

Modified files:
- gateway/api/router.py (added chat router include)
- gateway/main.py (added AdapterRegistry init in lifespan)
- gateway/core/exceptions.py (changed miner_uid type from int to str)
- gateway/middleware/error_handler.py (added subnet/miner_uid to error responses)
- tests/conftest.py (added adapter registry setup for tests)

### Change Log

- 2026-03-13: Implemented Story 1.4 — SN1 text generation endpoint with OpenAI-compatible chat completions API, fat-base/thin-adapter pattern, adapter registry, full test coverage (45 new tests, 148 total passing)
- 2026-03-13: Code review (Claude Opus 4.6) — 9 issues found (3 HIGH, 4 MEDIUM, 2 LOW). All added as review follow-up action items.
- 2026-03-13: Addressed all 9 code review findings — XSS sanitization expanded, Bittensor-disabled path fixed, error logging added, model echo, empty response handling, test fixtures improved, max_tokens validated. 155 tests passing.

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested

### Summary

Implementation follows the fat-base/thin-adapter architecture correctly. All 8 tasks and subtasks are genuinely complete with real tests. OpenAI-compatible request/response format is solid. However, 3 HIGH issues need addressing before merge: incomplete XSS sanitization, crash when Bittensor disabled, and missing error logging.

### Action Items

- [x] [HIGH] H1: Expand sanitize_output() — now strips ALL HTML tags
- [x] [HIGH] H2: `enable_bittensor=False` path now sets empty AdapterRegistry — graceful 503
- [x] [HIGH] H3: Added `chat_completion_error` log on GatewayError
- [x] [MEDIUM] M1: `from_response()` now echoes requested model via `request_data`
- [x] [MEDIUM] M2: Empty `dendrite.forward()` response → `MinerInvalidResponseError` (correct diagnosis)
- [x] [MEDIUM] M3: `_clean_state` fixture resets `app.state` singletons
- [x] [MEDIUM] M4: `max_tokens` has `ge=1` constraint
- [x] [LOW] L1: Removed unused `structlog` logger
- [x] [LOW] L2: Added `test_app` fixture — no more `client._transport.app`

### Severity Breakdown

| Severity | Count |
|----------|-------|
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 2 |
| **Total** | **9** |
