# Story 2.4: Adapter Registry & Extensibility

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want to add support for new subnets by registering a thin adapter class,
So that expanding gateway coverage doesn't require modifying core gateway code.

## Acceptance Criteria

1. **Given** the adapter registry module (`subnets/registry.py`), **when** a new subnet adapter is created following the base adapter pattern, **then** it can be registered by netuid → adapter instance mapping, **and** the gateway automatically includes it in `/v1/models` and `/v1/health`, **and** no changes to core gateway code (routing, auth, middleware) are required (FR45).

2. **Given** the base adapter class (`subnets/base.py`), **when** implementing a new subnet adapter, **then** the concrete adapter only needs to implement `to_synapse()`, `from_response()`, `sanitize_output()`, and `get_config()`, **and** miner selection, Dendrite query, response validation, sanitization, and usage metering are handled by the base class (FR46), **and** the concrete adapter is approximately 50 lines of code.

3. **Given** the three existing adapters (SN1, SN19, SN62), **when** I review their implementations, **then** each follows the same structural pattern via the base class, **and** subnet-specific logic is isolated to the thin adapter layer, **and** shared behavior is not duplicated across adapters.

## Tasks / Subtasks

- [x] Task 1: Add self-describing metadata to BaseAdapter (AC: #1, #2)
  - [x] 1.1: Add abstract method `get_capability() -> str` to `BaseAdapter` in `gateway/subnets/base.py`
  - [x] 1.2: Add abstract method `get_parameters() -> dict[str, str]` to `BaseAdapter`
  - [x] 1.3: Implement `get_capability()` and `get_parameters()` in all 3 adapters — data moved from hardcoded maps in `models.py` into each adapter

- [x] Task 2: Update /v1/models to use adapter self-description (AC: #1)
  - [x] 2.1: Removed `_CAPABILITY_MAP` and `_PARAMETER_MAP` from `gateway/api/models.py`
  - [x] 2.2: Updated `list_models()` to call `info.adapter.get_capability()` and `info.adapter.get_parameters()`
  - [x] 2.3: Added `adapter: BaseAdapter | None` field to `AdapterInfo` dataclass (Option A — simpler, no data duplication)
  - [x] 2.4: Verified — dynamically registered adapter auto-appears in `/v1/models` with correct metadata (test: `test_dynamic_adapter_appears_in_models`)

- [x] Task 3: Refactor adapter registration to be config-driven (AC: #1)
  - [x] 3.1: Created `ADAPTER_DEFINITIONS` in `gateway/subnets/__init__.py` — list of `(AdapterClass, model_names, netuid_setting_name)` tuples
  - [x] 3.2: Updated `gateway/main.py` lifespan to iterate `ADAPTER_DEFINITIONS` for adapter registration
  - [x] 3.3: Updated `gateway/main.py` lifespan to iterate `ADAPTER_DEFINITIONS` for metagraph registration and null checks
  - [x] 3.4: Verified — adding a new adapter requires only: (1) adapter file, (2) settings entry, (3) one line in `ADAPTER_DEFINITIONS`

- [x] Task 4: Verify structural consistency across adapters (AC: #3)
  - [x] 4.1: Audited — all 3 adapters follow: Synapse class → Adapter class with 6 abstract methods → `get_config()` returns `AdapterConfig`
  - [x] 4.2: Verified — no shared behavior duplicated; all common logic in `BaseAdapter.execute()` and `BaseAdapter.execute_stream()`
  - [x] 4.3: `BaseAdapter` already has module-level docstring describing the fat-base / thin-adapter pattern
  - [x] 4.4: Verified — SN1 streaming works via opt-in override; SN19/SN62 raise `NotImplementedError` (tested)

- [x] Task 5: Tests (AC: all)
  - [x] 5.1: Updated `tests/subnets/test_registry.py` — 3 new tests: adapter instance exposed, capability accessible, parameters accessible
  - [x] 5.2: Updated `tests/api/test_models.py` — 2 new tests: capabilities from self-description, dynamic adapter appears in response
  - [x] 5.3: Created `tests/subnets/test_adapter_pattern.py` — 14 tests: all adapters subclass BaseAdapter, implement required methods, return valid configs, no duplicate netuids/names, streaming opt-in
  - [x] 5.4: 396 tests pass (31 new + 365 existing), zero regressions
  - [x] 5.5: ruff check clean, mypy clean — zero errors

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Fat Base / Thin Adapter Pattern

The architecture mandates this pattern (already implemented):
- `BaseAdapter.execute()` handles: miner selection, Dendrite query, timeout → `MinerTimeoutError` (504), failure → `MinerInvalidResponseError` (502), response validation, sanitization, gateway headers
- `BaseAdapter.execute_stream()` handles: streaming lifecycle, SSE formatting, client disconnect detection
- Concrete adapters provide ONLY: `to_synapse()`, `from_response()`, `sanitize_output()`, `get_config()`

**What Story 2.4 adds:** Two new abstract methods for self-description:
- `get_capability() -> str` — e.g., "Text Generation", "Image Generation"
- `get_parameters() -> dict[str, str]` — informational parameter descriptions

These are metadata-only methods with no I/O. They make adapters self-describing so `/v1/models` doesn't need hardcoded maps.

#### Adapter Line Counts (Current State)

| Adapter | Lines | Includes Streaming |
|---|---|---|
| SN1TextAdapter | 147 | Yes (streaming synapse + format methods) |
| SN19ImageAdapter | 102 | No (includes image validation) |
| SN62CodeAdapter | 77 | No |

SN1 is larger because it includes streaming support (TextGenStreamingSynapse, format_stream_chunk, format_stream_done). SN19 is larger because it includes base64 image header validation. SN62 is the cleanest minimal example at ~77 lines. Adding `get_capability()` and `get_parameters()` adds ~10-15 lines to each adapter.

#### Config-Driven Registration

Currently `main.py` hardcodes:
```python
adapter_registry.register(SN1TextAdapter(), model_names=["tao-sn1"])
adapter_registry.register(SN19ImageAdapter(), model_names=["tao-sn19"])
adapter_registry.register(SN62CodeAdapter(), model_names=["tao-sn62"])
```

Replace with a data-driven approach in `gateway/subnets/__init__.py`:
```python
from gateway.subnets.sn1_text import SN1TextAdapter
from gateway.subnets.sn19_image import SN19ImageAdapter
from gateway.subnets.sn62_code import SN62CodeAdapter

ADAPTER_DEFINITIONS: list[tuple[type[BaseAdapter], list[str], str]] = [
    (SN1TextAdapter, ["tao-sn1"], "sn1_netuid"),
    (SN19ImageAdapter, ["tao-sn19"], "sn19_netuid"),
    (SN62CodeAdapter, ["tao-sn62"], "sn62_netuid"),
]
```

Then `main.py` iterates this list. Adding a new subnet means:
1. Create `gateway/subnets/sn_NEW.py` (adapter + synapse)
2. Add `sn_new_netuid` and `sn_new_timeout_seconds` to `Settings`
3. Add one tuple to `ADAPTER_DEFINITIONS`

No changes to `main.py`, `router.py`, `models.py`, `health.py`, or any middleware.

#### AdapterInfo Enhancement

`AdapterInfo` currently has `config` and `model_names`. To support self-describing models, either:
- **Option A:** Add `adapter: BaseAdapter` reference to `AdapterInfo` — callers call `adapter.get_capability()` directly
- **Option B:** Add `capability: str` and `parameters: dict[str, str]` to `AdapterInfo` — populated at registration time

**Prefer Option A** — simpler, no data duplication, and the adapter instance is already available in the registry.

#### `/v1/models` After This Story

The `_CAPABILITY_MAP` and `_PARAMETER_MAP` in `gateway/api/models.py` are deleted. Instead:
```python
for info in registry.list_all():
    adapter = info.adapter  # New field
    capability = adapter.get_capability()
    parameters = adapter.get_parameters()
    ...
```

This means any new adapter that implements `get_capability()` and `get_parameters()` automatically appears in `/v1/models` with correct metadata. No hardcoded maps to update.

### Previous Story Intelligence (Story 2.3)

**Patterns established that MUST be followed:**
- `structlog` for all logging — never `print()` or stdlib `logging`
- `Depends()` for request-scoped dependencies, `app.state` for singletons
- Response validated against Pydantic schema before returning
- Defensive copies in `list_all()` for model_names (Round 2 review finding)
- No auth on `/v1/models` or `/v1/health` — public discovery endpoints
- `_sanitize_sync_error()` errors logged at source, not re-logged in health endpoint

**Learnings from code reviews (2 rounds, 10 issues on Story 2.3):**
- Don't expose internal details in public responses (SEC-010)
- Avoid module-level timestamps — use `app.state.start_time`
- Test the `enable_bittensor=False` path
- Make tests self-documenting — explicit state setup, not implicit conftest reliance
- Defensive copies for mutable internal state exposed via public API

**Git intelligence — recent patterns (last 5 commits):**
- Test count: 365 tests passing as of latest commit (Story 2.3)
- Clean ruff/mypy on all new code
- Adapter pattern well-established across 3 subnets

### Library & Framework Requirements

No new dependencies needed — everything is already in pyproject.toml.

### Project Structure Notes

**Modified files:**
- `gateway/subnets/base.py` — Add `get_capability()` and `get_parameters()` abstract methods
- `gateway/subnets/sn1_text.py` — Implement `get_capability()` and `get_parameters()`
- `gateway/subnets/sn19_image.py` — Implement `get_capability()` and `get_parameters()`
- `gateway/subnets/sn62_code.py` — Implement `get_capability()` and `get_parameters()`
- `gateway/subnets/registry.py` — Add `adapter` field to `AdapterInfo`
- `gateway/subnets/__init__.py` — Add `ADAPTER_DEFINITIONS` list
- `gateway/api/models.py` — Remove hardcoded maps, use adapter self-description
- `gateway/main.py` — Iterate `ADAPTER_DEFINITIONS` instead of hardcoded registration

**New test files:**
- `tests/subnets/test_adapter_pattern.py` — Structural consistency tests

**Modified test files:**
- `tests/subnets/test_registry.py` — AdapterInfo adapter field tests
- `tests/api/test_models.py` — Self-description integration tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.4] — Full acceptance criteria
- [Source: _bmad-output/planning-artifacts/prd.md#FR45] — No changes to core gateway code for new subnets
- [Source: _bmad-output/planning-artifacts/prd.md#FR46] — Base class handles shared behavior
- [Source: _bmad-output/planning-artifacts/architecture.md#API-&-Communication-Patterns] — Fat base / thin adapter pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure] — `gateway/subnets/` organization
- [Source: _bmad-output/implementation-artifacts/2-3-subnet-discovery-and-health.md] — Previous story patterns, 365 tests
- [Source: gateway/subnets/base.py] — BaseAdapter ABC with execute() fat base
- [Source: gateway/subnets/registry.py] — AdapterRegistry with list_all(), AdapterInfo
- [Source: gateway/api/models.py] — Hardcoded _CAPABILITY_MAP and _PARAMETER_MAP to remove
- [Source: gateway/main.py:109-112] — Hardcoded adapter registration to refactor

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- Added `get_capability()` and `get_parameters()` abstract methods to `BaseAdapter` — adapters are now self-describing
- Implemented self-description in all 3 adapters: SN1 ("Text Generation"), SN19 ("Image Generation"), SN62 ("Code Generation")
- Added `adapter: BaseAdapter | None` field to `AdapterInfo` dataclass — callers access metadata directly via adapter reference
- Removed hardcoded `_CAPABILITY_MAP` and `_PARAMETER_MAP` from `gateway/api/models.py` — `/v1/models` now uses adapter self-description
- Created `ADAPTER_DEFINITIONS` in `gateway/subnets/__init__.py` — config-driven adapter registration
- Refactored `main.py` lifespan to iterate `ADAPTER_DEFINITIONS` for both metagraph and adapter registration — eliminated 3 hardcoded blocks
- Updated all test stub/fake adapters (`FakeAdapter`, `FakeStreamAdapter`, `StubAdapter`) with new abstract methods
- Created `test_adapter_pattern.py` with 14 parametrized tests verifying structural consistency across all adapters
- 387 tests pass (22 new, 9 redundant tests removed in review), ruff clean, mypy clean

### Change Log

- 2026-03-13: Implemented Story 2.4 — adapter self-description, config-driven registration, structural consistency verification. Removed hardcoded maps from models endpoint. 396 tests passing (31 new).
- 2026-03-13: Code review round 1 (Claude Opus 4.6) — 5 issues found (0 HIGH, 2 MEDIUM, 3 LOW). Fixed: derived ALL_ADAPTERS from ADAPTER_DEFINITIONS, updated conftest to use ADAPTER_DEFINITIONS for registration and reset, removed redundant hasattr tests. 387 tests passing (9 redundant tests removed).

### File List

Modified files:
- gateway/subnets/base.py
- gateway/subnets/sn1_text.py
- gateway/subnets/sn19_image.py
- gateway/subnets/sn62_code.py
- gateway/subnets/registry.py
- gateway/subnets/__init__.py
- gateway/api/models.py
- gateway/main.py
- tests/subnets/test_registry.py
- tests/subnets/test_base_adapter.py
- tests/subnets/test_base_adapter_streaming.py
- tests/api/test_models.py

New files:
- tests/subnets/test_adapter_pattern.py

## Senior Developer Review (AI)

### Round 1

**Reviewer:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-13
**Outcome:** Changes Requested -> All Fixed

- [x] [MEDIUM] M1: `test_adapter_pattern.py` hardcoded `ALL_ADAPTERS` instead of deriving from `ADAPTER_DEFINITIONS` — fixed to use `ADAPTER_DEFINITIONS`
- [x] [MEDIUM] M2: `conftest.py` hardcoded adapter/metagraph registration instead of using `ADAPTER_DEFINITIONS` — refactored to iterate `ADAPTER_DEFINITIONS` for registration and reset
- [x] [LOW] L1: `AdapterInfo.adapter` typed as `None`-able but always set — kept as-is (dataclass ordering requires default; defensive checks in models.py handle it)
- [x] [LOW] L2: Redundant `hasattr` tests removed — `@abstractmethod` already enforces method existence via instantiation
- [x] [LOW] L3: `get_parameters()` creates fresh dicts per call — kept as-is (safer than class-level constants, consistent with defensive-copy pattern)

| Severity | Count |
|----------|-------|
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 3 |
| **Total** | **5** |
