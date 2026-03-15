# Code Review Fixes — Round 10 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 10 issues (3 HIGH, 5 MEDIUM, 2 LOW) found during adversarial code review of Stories 1.1, 1.2, and 1.3 on main.

**Architecture:** All fixes are surgical — targeted changes to existing files with no new modules. The health endpoint gets a resilient Redis dependency, docker-compose gets wallet support and stronger secret validation, tests get expanded coverage for untested business rules, and minor optimizations land in rate limiting and health caching.

**Tech Stack:** Python 3.12, FastAPI, Redis (async), SQLAlchemy (async), argon2-cffi, structlog, pytest + pytest-asyncio, Docker Compose

---

## Context for the Implementer

This codebase is a FastAPI gateway for the Bittensor decentralized AI network. It has:
- **Auth layer:** JWT for dashboard, API keys (argon2-hashed) for API access, Redis 60s cache
- **Bittensor layer:** Wallet loading, metagraph sync (background task), miner selection
- **Health endpoint:** Reports DB, Redis, and metagraph status; has 5s in-memory cache
- **Tests:** 95 tests, all passing. Use `uv run pytest` to run. Tests mock Bittensor SDK and use a real test Postgres + Redis.

Key patterns:
- `gateway/core/redis.py` — singleton Redis client with circuit breaker (5s cooldown) and `reset_redis()` for reconnection
- `gateway/middleware/auth.py` — uses `_try_get_redis()` pattern for optional Redis (falls through to DB-only on failure)
- `gateway/api/health.py` — `Depends(get_redis)` for Redis access (this is the bug — crashes instead of degrading)
- `tests/conftest.py` — sets `DATABASE_URL` to test DB before any imports, mocks Bittensor SDK globally

Run tests: `uv run pytest --tb=short -q`
Run linter: `uv run ruff check gateway/ tests/`
Run type checker: `uv run mypy gateway/`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `gateway/api/health.py` | Modify | H1: resilient Redis dependency; L1: cache dict not model |
| `gateway/core/config.py` | Modify | H3: block known-weak JWT secrets |
| `docker-compose.yml` | Modify | H2: add wallet volume mount + ENABLE_BITTENSOR flag |
| `gateway/main.py` | Modify | H2: make Bittensor init conditional on setting |
| `gateway/core/config.py` | Modify | H2: add `enable_bittensor` setting |
| `gateway/api/auth.py` | Modify | M4: register Lua script for SHA caching |
| `.env.example` | Modify | M5: remove APP_VERSION line |
| `tests/api/test_health.py` | Modify | H1+M2: test Redis-down degradation |
| `tests/api/test_api_keys.py` | Modify | M1: test MAX_KEYS_PER_ORG limit |
| `gateway/api/health.py` | Modify | L2: add more sync error categories |

---

## Chunk 1: HIGH Fixes

### Task 1: H1 — Health endpoint resilient Redis dependency

The health endpoint uses `Depends(get_redis)` which raises `ConnectionError` when the circuit breaker is open. It should degrade gracefully instead.

**Files:**
- Modify: `gateway/api/health.py:86-91` — replace `Depends(get_redis)` with inline optional Redis
- Create test: `tests/api/test_health.py` — add Redis-down degradation test (also covers M2)

- [ ] **Step 1: Write the failing test for Redis-down health degradation**

Add to `tests/api/test_health.py`:

```python
@pytest.mark.asyncio
async def test_health_degraded_when_redis_down(client: AsyncClient) -> None:
    """Health returns degraded (not 500) when Redis is completely unavailable."""
    from unittest.mock import AsyncMock

    from gateway.api.health import clear_health_cache
    from gateway.core.redis import get_redis
    from gateway.main import app

    clear_health_cache()

    # Use dependency_overrides (same pattern as test_health_degraded_when_db_down)
    # to demonstrate the current 500 crash. After the fix, this test switches to
    # patching the module-level _get_redis alias instead.
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = ConnectionError("Redis unavailable")

    async def _broken_redis():  # type: ignore[no-untyped-def]
        return mock_redis

    app.dependency_overrides[get_redis] = _broken_redis
    try:
        response = await client.get("/v1/health")
        data = response.json()
        assert response.status_code == 503
        assert data["status"] == "degraded"
        assert data["redis"] == "unhealthy"
    finally:
        app.dependency_overrides.pop(get_redis, None)
        clear_health_cache()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_health.py::test_health_degraded_when_redis_down -v`
Expected: FAIL — 500 error because `Depends(get_redis)` raises `ConnectionError` before handler runs

- [ ] **Step 3: Fix health endpoint to use optional Redis**

In `gateway/api/health.py`, replace the route signature and add a helper:

Change the imports — add:
```python
from gateway.core.redis import get_redis as _get_redis
```

Remove `get_redis` from the existing imports (it's imported from `gateway.core.redis`).

Replace the `health_check` function (lines 86-136) with:

```python
async def _try_get_redis_for_health() -> Redis | None:
    """Best-effort Redis for health checks. Returns None if unavailable."""
    try:
        return await _get_redis()
    except Exception:
        return None


@router.get("/v1/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    now = time.monotonic()
    cached_time = _health_cache.get("time")
    if cached_time is not None and now - cached_time < _HEALTH_CACHE_TTL:
        return JSONResponse(content=_health_cache["result"], status_code=200)

    db_status = "healthy"
    redis_status = "healthy"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
        logger.warning("health_check_db_failed")

    redis = await _try_get_redis_for_health()
    if redis is None:
        redis_status = "unhealthy"
        logger.warning("health_check_redis_failed")
    else:
        try:
            await redis.ping()  # type: ignore[misc]
        except Exception:
            redis_status = "unhealthy"
            logger.warning("health_check_redis_failed")

    metagraph_status = _get_metagraph_status(request)
    metagraph_stale = False
    if metagraph_status:
        metagraph_stale = any(s.is_stale for s in metagraph_status.values())

    is_healthy = db_status == redis_status == "healthy" and not metagraph_stale
    overall = "healthy" if is_healthy else "degraded"
    result = HealthResponse(
        status=overall,
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
        metagraph=metagraph_status,
    )

    # Only cache healthy responses so degraded state is not sticky.
    # Cache the serialized dict to avoid repeated model_dump() calls (L1).
    if is_healthy:
        _health_cache["result"] = result.model_dump()
        _health_cache["time"] = now
    else:
        _health_cache.clear()

    status_code = 200 if is_healthy else 503
    return JSONResponse(content=result.model_dump(), status_code=status_code)
```

Note: This also fixes **L1** (cache stores dict, not model) by caching `result.model_dump()` and returning it directly on cache hit.

Remove the `Redis` import from the `Depends` usage (it's no longer a dependency parameter). Keep the `Redis` import for the type annotation on `_try_get_redis_for_health`. Also remove the unused `from gateway.core.redis import get_redis` import line — replaced by the aliased `_get_redis`.

- [ ] **Step 4: Update test to use the new `_get_redis` patch pattern**

Now that `_get_redis` exists in `gateway.api.health`, replace the test written in Step 1 with the proper version that patches the module-level alias (this is what will be tested going forward — the dependency_overrides version was only to demonstrate the pre-fix crash):

```python
@pytest.mark.asyncio
async def test_health_degraded_when_redis_down(client: AsyncClient) -> None:
    """Health returns degraded (not 500) when Redis is completely unavailable."""
    from unittest.mock import patch

    from gateway.api.health import clear_health_cache

    clear_health_cache()

    with patch(
        "gateway.api.health._get_redis",
        side_effect=ConnectionError("Redis unavailable (circuit breaker open)"),
    ):
        response = await client.get("/v1/health")
        data = response.json()
        assert response.status_code == 503
        assert data["status"] == "degraded"
        assert data["redis"] == "unhealthy"
    clear_health_cache()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: ALL health tests PASS including the new one

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: 96 passed (95 + 1 new)

- [ ] **Step 7: Run linter and type checker**

Run: `uv run ruff check gateway/api/health.py tests/api/test_health.py`
Run: `uv run mypy gateway/api/health.py`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add gateway/api/health.py tests/api/test_health.py
git commit -m "fix: health endpoint degrades gracefully when Redis unreachable

Health check used Depends(get_redis) which crashes with 500 when the
circuit breaker is open. Now uses inline optional Redis — returns
degraded with redis=unhealthy instead of crashing.

Also caches serialized dict instead of Pydantic model (minor optimization)."
```

---

### Task 2: H2 — Make Bittensor init conditional + add wallet volume to docker-compose

`docker compose up` fails because the container has no wallet files. Fix by making Bittensor init optional via an `ENABLE_BITTENSOR` setting (defaults true in production, false for local dev).

**Files:**
- Modify: `gateway/core/config.py` — add `enable_bittensor: bool` setting
- Modify: `gateway/main.py:45-81` — wrap Bittensor init in conditional
- Modify: `docker-compose.yml` — add wallet volume mount + `ENABLE_BITTENSOR` env var
- Modify: `.env.example` — add `ENABLE_BITTENSOR` entry
- Modify: `tests/core/test_lifespan.py` — add test for Bittensor-disabled startup

- [ ] **Step 1: Add `enable_bittensor` setting to config**

In `gateway/core/config.py`, add to the Bittensor section of the `Settings` class (after `dendrite_timeout_seconds`):

```python
    enable_bittensor: bool = True
```

- [ ] **Step 2: Write failing test for Bittensor-disabled startup**

Add to `tests/core/test_lifespan.py`:

```python
class TestLifespanBittensorDisabled:
    """Test that lifespan succeeds without Bittensor when disabled."""

    @pytest.mark.asyncio
    async def test_startup_succeeds_without_bittensor(self) -> None:
        """When enable_bittensor=False, gateway starts without wallet/subtensor."""
        with (
            patch("gateway.main.settings") as mock_settings,
            patch("gateway.main.get_engine") as mock_engine,
            patch("gateway.main.get_redis") as mock_redis,
            patch("gateway.main.close_redis", new_callable=AsyncMock),
        ):
            # Configure mock settings
            mock_settings.enable_bittensor = False
            mock_settings.app_version = "0.0.0-test"

            mock_conn = AsyncMock()
            mock_engine_instance = MagicMock()
            mock_engine_instance.connect.return_value.__aenter__ = AsyncMock(
                return_value=mock_conn
            )
            mock_engine_instance.connect.return_value.__aexit__ = AsyncMock()
            mock_engine_instance.dispose = AsyncMock()
            mock_engine.return_value = mock_engine_instance

            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            from fastapi import FastAPI

            from gateway.main import lifespan

            test_app = FastAPI()
            async with lifespan(test_app):
                # Bittensor state should NOT be set
                assert not hasattr(test_app.state, "dendrite")
                assert not hasattr(test_app.state, "metagraph_manager")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/test_lifespan.py::TestLifespanBittensorDisabled -v`
Expected: FAIL — lifespan still tries to init Bittensor

- [ ] **Step 4: Wrap Bittensor init in conditional in `gateway/main.py`**

Replace lines 45-82 (from `# Bittensor SDK initialization` through `logger.info("startup_bittensor_ok")`) with:

```python
    # Bittensor SDK initialization (optional — disable for local dev without wallet)
    if settings.enable_bittensor:
        try:
            wallet = create_wallet()
            subtensor = create_subtensor()
            dendrite = create_dendrite(wallet)
        except Exception as exc:
            logger.error("startup_bittensor_failed", error=str(exc), error_type=type(exc).__name__)
            raise

        metagraph_manager = MetagraphManager(
            subtensor=subtensor,
            sync_interval=settings.metagraph_sync_interval_seconds,
            sync_timeout=settings.dendrite_timeout_seconds,
        )
        metagraph_manager.register_subnet(settings.sn1_netuid)
        await metagraph_manager.start()

        try:
            if metagraph_manager.get_metagraph(settings.sn1_netuid) is None:
                logger.error(
                    "startup_metagraph_empty",
                    netuid=settings.sn1_netuid,
                )
                raise RuntimeError(
                    f"Initial metagraph sync failed for SN{settings.sn1_netuid} — "
                    "cannot route requests without metagraph data"
                )
        except BaseException:
            await metagraph_manager.stop()
            raise

        miner_selector = MinerSelector(metagraph_manager)

        app.state.dendrite = dendrite
        app.state.metagraph_manager = metagraph_manager
        app.state.miner_selector = miner_selector

        logger.info("startup_bittensor_ok")
    else:
        logger.info("startup_bittensor_skipped")
        dendrite = None
        metagraph_manager = None
```

Update shutdown section — replace the metagraph and dendrite shutdown blocks with:

```python
    # Shutdown — each step guarded so one failure doesn't skip the rest
    if metagraph_manager is not None:
        try:
            await metagraph_manager.stop()
        except Exception:
            logger.warning("shutdown_metagraph_manager_failed", exc_info=True)
    if dendrite is not None:
        try:
            await dendrite.aclose_session()
        except Exception:
            logger.warning("shutdown_dendrite_close_failed", exc_info=True)
```

Keep the engine dispose and close_redis as-is.

- [ ] **Step 5: Update docker-compose.yml**

Add `ENABLE_BITTENSOR` env var and wallet volume:

```yaml
  gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-tao}:${POSTGRES_PASSWORD:-tao}@postgres:5432/${POSTGRES_DB:-tao_gateway}
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=${DEBUG:-true}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-only-insecure-key-do-not-use-in-prod}
      - ENABLE_BITTENSOR=${ENABLE_BITTENSOR:-false}
      - WALLET_PATH=/app/.bittensor/wallets
    volumes:
      - ${WALLET_PATH:-./.bittensor/wallets}:/app/.bittensor/wallets:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

Note: `ENABLE_BITTENSOR` defaults to `false` for local dev (docker compose up works without wallets). Production deployments set `ENABLE_BITTENSOR=true` and mount wallet files.

**Important:** The container wallet path is `/app/.bittensor/wallets` (the WORKDIR), not `~/.bittensor/wallets`. The Dockerfile creates user `app` with `useradd --system` which doesn't guarantee a `/home/app` home directory. The `WALLET_PATH` env var inside the container overrides `settings.wallet_path` so the Bittensor SDK finds the mounted files. The host-side default uses `./.bittensor/wallets` (project-relative) — users must set `WALLET_PATH` to their actual host wallet location for production.

- [ ] **Step 6: Update `.env.example`**

Add after the Bittensor section:

```
ENABLE_BITTENSOR=true
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest --tb=short -q`
Expected: 97+ passed

- [ ] **Step 8: Commit**

```bash
git add gateway/core/config.py gateway/main.py docker-compose.yml .env.example tests/core/test_lifespan.py
git commit -m "fix: make Bittensor init conditional — docker compose up works without wallets

Added ENABLE_BITTENSOR setting (default true). When false, gateway
starts without wallet/subtensor/metagraph — useful for local dev.
docker-compose defaults to false so fresh clone starts successfully.
Added wallet volume mount for when Bittensor is enabled."
```

---

### Task 3: H3 — Block known-weak JWT secrets in validation

The docker-compose default JWT key passes production validation because only the literal `"change-me-in-production"` is blocked.

**Files:**
- Modify: `gateway/core/config.py:9,52-69` — expand insecure secret detection
- Add test: `tests/core/test_config.py` (new file) — test weak secret rejection

- [ ] **Step 1: Write failing test for docker-compose default being rejected**

Create `tests/core/test_config.py`:

```python
import os
from unittest.mock import patch

import pytest


class TestJwtSecretValidation:
    def test_rejects_insecure_default_in_production(self) -> None:
        """The hardcoded insecure default is rejected when DEBUG=false."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
            Settings(
                debug=False,
                jwt_secret_key="change-me-in-production",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_rejects_docker_compose_default_in_production(self) -> None:
        """The docker-compose dev-only key is rejected in production."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                debug=False,
                jwt_secret_key="dev-only-insecure-key-do-not-use-in-prod",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_rejects_key_containing_insecure_markers(self) -> None:
        """Keys containing 'insecure', 'change-me', or 'do-not-use' are rejected."""
        from gateway.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings(
                debug=False,
                jwt_secret_key="a]" * 20 + "insecure",
                database_url="postgresql+asyncpg://x:x@localhost/x",
            )

    def test_accepts_strong_secret_in_production(self) -> None:
        """A 64-char hex secret passes validation."""
        from gateway.core.config import Settings

        s = Settings(
            debug=False,
            jwt_secret_key="a" * 64,
            database_url="postgresql+asyncpg://x:x@localhost/x",
        )
        assert s.jwt_secret_key == "a" * 64

    def test_allows_insecure_default_in_debug(self) -> None:
        """Debug mode allows the insecure default with a warning."""
        import warnings

        from gateway.core.config import Settings

        # Force all warnings to be raised — Python's default filter suppresses
        # duplicate warnings from the same source location, which can cause
        # pytest.warns to miss the warning if another test triggered it first.
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            with pytest.warns(UserWarning, match="insecure default"):
                s = Settings(
                    debug=True,
                    jwt_secret_key="change-me-in-production",
                    database_url="postgresql+asyncpg://x:x@localhost/x",
                )
        assert s.jwt_secret_key == "change-me-in-production"
```

- [ ] **Step 2: Run test to verify docker-compose default test fails**

Run: `uv run pytest tests/core/test_config.py::TestJwtSecretValidation::test_rejects_docker_compose_default_in_production -v`
Expected: FAIL — current validator accepts this key

- [ ] **Step 3: Update JWT secret validation in config.py**

Replace the `validate_jwt_secret` method in `gateway/core/config.py`:

Add `_INSECURE_MARKERS` at module level, right after `_MIN_JWT_SECRET_LENGTH` (line 10):

```python
_INSECURE_MARKERS = ["change-me", "insecure", "do-not-use", "example", "placeholder"]
```

Then replace the `validate_jwt_secret` method (lines 52-70) with:

```python
    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        secret = self.jwt_secret_key
        if secret == _INSECURE_DEFAULT_SECRET:
            if self.debug:
                warnings.warn(
                    "JWT_SECRET_KEY is using the insecure default. Set JWT_SECRET_KEY in your env.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        elif not self.debug:
            # Block any key containing known insecure markers
            lower = secret.lower()
            if any(marker in lower for marker in _INSECURE_MARKERS):
                raise ValueError(
                    "JWT_SECRET_KEY contains an insecure marker and cannot be used in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            if len(secret) < _MIN_JWT_SECRET_LENGTH:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_LENGTH} characters. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        return self
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/test_config.py -v`
Expected: ALL PASS

Run: `uv run pytest --tb=short -q`
Expected: all pass (existing + new)

- [ ] **Step 5: Commit**

```bash
git add gateway/core/config.py tests/core/test_config.py
git commit -m "fix: block known-weak JWT secrets in production validation

Validator now rejects keys containing insecure markers (change-me,
insecure, do-not-use, example, placeholder) — not just the single
hardcoded default. Prevents docker-compose dev keys from passing
production validation."
```

---

## Chunk 2: MEDIUM + LOW Fixes

### Task 4: M1 — Test MAX_KEYS_PER_ORG limit

**Files:**
- Modify: `tests/api/test_api_keys.py` — add per-org key limit test

- [ ] **Step 1: Write the test**

Add to `tests/api/test_api_keys.py`. This test needs a real org in the DB, so it requires signup + login flow:

```python
@pytest.mark.asyncio
async def test_create_api_key_rejects_when_limit_reached(client: AsyncClient) -> None:
    """Creating more than MAX_KEYS_PER_ORG active keys returns 422."""
    from unittest.mock import patch

    # Create a real org via signup
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": "keylimit@test.com", "password": "testpass123"},
    )
    assert signup_resp.status_code == 201

    # Login to get JWT
    login_resp = await client.post(
        "/auth/login",
        json={"email": "keylimit@test.com", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Temporarily lower the limit to make the test fast
    with patch("gateway.services.api_key_service.MAX_KEYS_PER_ORG", 3):
        for i in range(3):
            resp = await client.post(
                "/dashboard/api-keys",
                json={"environment": "test"},
                headers=headers,
            )
            assert resp.status_code == 201, f"Key {i+1} failed: {resp.text}"

        # 4th key should be rejected
        resp = await client.post(
            "/dashboard/api-keys",
            json={"environment": "test"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "Maximum" in resp.json()["error"]["message"]
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/api/test_api_keys.py::test_create_api_key_rejects_when_limit_reached -v`
Expected: PASS (the code already enforces this — we're just adding the missing test)

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_api_keys.py
git commit -m "test: add coverage for MAX_KEYS_PER_ORG limit enforcement"
```

---

### Task 5: M4 — Register Lua rate limit script for SHA caching

**Files:**
- Modify: `gateway/api/auth.py:19-25,51-53` — use `register_script` instead of `eval`

- [ ] **Step 1: Refactor rate limit to use registered script**

In `gateway/api/auth.py`, replace the Lua script usage. Change the script constant and the usage in `_rate_limit_auth`:

Replace lines 19-25 (`_RATE_LIMIT_LUA` and its docstring) and lines 49-53 (the `redis.eval` call):

The Lua script text stays the same but gets registered lazily, with instance tracking to handle Redis reconnection:

```python
_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""
_rate_limit_script: object | None = None
_rate_limit_script_redis: object | None = None  # track which Redis instance owns the script
```

In `_rate_limit_auth`, replace the redis.eval block:

```python
    try:
        redis = await get_redis()
        global _rate_limit_script, _rate_limit_script_redis  # noqa: PLW0603
        # Re-register if Redis instance changed (e.g., after reset_redis() reconnection)
        if _rate_limit_script is None or _rate_limit_script_redis is not redis:
            _rate_limit_script = redis.register_script(_RATE_LIMIT_LUA)
            _rate_limit_script_redis = redis
        raw_result = await _rate_limit_script(keys=[key], args=[60])
        current = int(raw_result)
    except Exception:
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `uv run pytest tests/api/test_auth.py -v`
Expected: ALL PASS

Run: `uv run ruff check gateway/api/auth.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add gateway/api/auth.py
git commit -m "perf: use registered Lua script for rate limiting

redis.register_script() caches the script server-side by SHA.
Subsequent calls send only the SHA instead of the full script body,
reducing network payload per rate limit check."
```

---

### Task 6: M5 — Remove APP_VERSION from .env.example

**Files:**
- Modify: `.env.example:12` — remove `APP_VERSION` line

- [ ] **Step 1: Remove the misleading line**

In `.env.example`, remove:
```
APP_VERSION=0.1.0
```

The version is derived from package metadata in `config.py`. An env var override would hide the real installed version.

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "fix: remove APP_VERSION from .env.example

Version is derived from package metadata (importlib.metadata).
Having it in .env.example invites overriding with a stale value."
```

---

### Task 7: M3 — Note about Alembic test gap (documentation only)

M3 (Alembic migrations untested) is not fixable in a unit test — it requires a real database migration run. This is tracked as a future CI improvement, not a code fix.

- [ ] **Step 1: No code change needed**

This is an advisory finding. The proper fix is adding an Alembic migration test to CI that runs `alembic upgrade head` against a clean database. This is out of scope for this round — document it and move on.

---

### Task 8: L2 — Expand sync error categories in health endpoint

**Files:**
- Modify: `gateway/api/health.py:33-38` — add more error categories

- [ ] **Step 1: Expand the error category mapping**

In `gateway/api/health.py`, replace `_SYNC_ERROR_CATEGORIES`:

```python
_SYNC_ERROR_CATEGORIES: dict[str, str] = {
    "timeout": "timeout",
    "timed out": "timeout",
    "connection": "connection_error",
    "unreachable": "connection_error",
    "refused": "connection_error",
    "reset": "connection_error",
    "ssl": "ssl_error",
    "certificate": "ssl_error",
    "dns": "dns_error",
    "resolve": "dns_error",
    "authentication": "auth_error",
    "permission": "auth_error",
}
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add gateway/api/health.py
git commit -m "improve: expand sync error categories in health endpoint

Added SSL, DNS, and auth error categories for better operational
visibility when metagraph sync fails."
```

---

### Task 9: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest --tb=short -q`
Expected: 98+ passed (95 original + new tests)

- [ ] **Step 2: Run linter**

Run: `uv run ruff check gateway/ tests/`
Expected: no errors

- [ ] **Step 3: Run type checker**

Run: `uv run mypy gateway/`
Expected: no errors (in files we modified)

- [ ] **Step 4: Update story change logs**

Add a change log entry to each story file:

`_bmad-output/implementation-artifacts/1-1-project-scaffold-and-health-endpoint.md` — append to Change Log:
```
- 2026-03-13: Tenth adversarial code review — fixed 1 HIGH (health endpoint crashes 500 when Redis unreachable after circuit breaker opens → now degrades gracefully) + 1 MEDIUM (APP_VERSION in .env.example overrides package metadata). Health cache now stores serialized dict.
```

`_bmad-output/implementation-artifacts/1-2-developer-account-and-api-key-creation.md` — append to Change Log:
```
- 2026-03-13: Tenth adversarial code review — fixed 1 HIGH (docker-compose JWT default passes production validation → expanded insecure marker detection) + 2 MEDIUM (missing MAX_KEYS_PER_ORG test, rate limit Lua script sent as full text per request → registered script). N tests pass.
```

`_bmad-output/implementation-artifacts/1-3-bittensor-integration-and-miner-selection.md` — append to Change Log:
```
- 2026-03-13: Tenth adversarial code review — fixed 1 HIGH (docker compose up fails without wallet → Bittensor init now conditional via ENABLE_BITTENSOR setting) + 1 LOW (expanded sync error categories in health endpoint). N tests pass.
```

- [ ] **Step 5: Final commit**

```bash
git add _bmad-output/implementation-artifacts/
git commit -m "docs: update story change logs with round 10 review fixes"
```
