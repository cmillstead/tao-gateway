# Story 1.2: Developer Account & API Key Creation

Status: done

## Story

As a **developer**,
I want to create an account and generate an API key via the API,
So that I can authenticate my requests to the gateway.

## Acceptance Criteria

1. **Given** I am a new user, **when** I send `POST /auth/signup` with email and password, **then** I receive a 201 response with account confirmation and the password is never stored in plaintext (argon2 hash only).

2. **Given** I have an account, **when** I send `POST /auth/login` with valid credentials, **then** I receive a JWT token for subsequent authenticated requests.

3. **Given** I am authenticated with a JWT, **when** I send `POST /dashboard/api-keys`, **then** I receive the full API key exactly once (prefixed `tao_sk_live_` or `tao_sk_test_`) and the key is stored as an argon2 hash in PostgreSQL (never plaintext), with only the key prefix stored in plaintext for identification.

4. **Given** I have an API key, **when** I send a request with `Authorization: Bearer tao_sk_live_...`, **then** the auth middleware validates the key via Redis cache (cache hit) or DB lookup + argon2 verify (cache miss), and the validated key ID is available to downstream handlers via `FastAPI Depends()`.

5. **Given** I send a request with an invalid or missing API key, **when** the auth middleware processes the request, **then** I receive a 401 response with the standard error envelope and the invalid key is redacted from all logs.

6. **Given** the Redis key cache, **when** a key is validated against the database, **then** the result is cached in Redis with a 60-second TTL and subsequent requests within the TTL skip the DB + argon2 verification (NFR3: <10ms validation).

## Tasks / Subtasks

- [x] Task 1: Database models and Alembic migration (AC: #1, #3, #4)
  - [x] 1.1: Create `gateway/models/organization.py` — SQLAlchemy `Organization` model with `organizations` table
  - [x] 1.2: Create `gateway/models/api_key.py` — SQLAlchemy `ApiKey` model with `api_keys` table
  - [x] 1.3: Update `gateway/models/__init__.py` to export both models (needed for Alembic autogenerate)
  - [x] 1.4: Update `migrations/env.py` to import models so Alembic can detect them for autogenerate
  - [x] 1.5: Generate Alembic migration: `uv run alembic revision --autogenerate -m "create organizations and api keys tables"`
  - [x] 1.6: Review and clean up generated migration file in `migrations/versions/`
  - [x] 1.7: Apply migration: `uv run alembic upgrade head` (requires postgres running)

- [x] Task 2: Pydantic schemas (AC: #1, #2, #3)
  - [x] 2.1: Create `gateway/schemas/auth.py` — `SignupRequest`, `SignupResponse`, `LoginRequest`, `LoginResponse` (with `access_token`, `token_type`)
  - [x] 2.2: Create `gateway/schemas/api_keys.py` — `ApiKeyCreateRequest`, `ApiKeyCreateResponse` (shows full key once), `ApiKeyListItem` (masked, prefix only)

- [x] Task 3: Service layer (AC: #1, #2, #3, #6)
  - [x] 3.1: Create `gateway/services/auth_service.py` — `signup()`, `login()`, `create_jwt_token()`, `verify_jwt_token()` using `argon2-cffi` for password hashing and `python-jose` for JWT
  - [x] 3.2: Create `gateway/services/api_key_service.py` — `generate_api_key()` (generate prefix + random suffix, hash full key), `list_keys()`, `revoke_key()`

- [x] Task 4: API route handlers (AC: #1, #2, #3)
  - [x] 4.1: Create `gateway/api/auth.py` — `POST /auth/signup` (201), `POST /auth/login` (200 with JWT)
  - [x] 4.2: Create `gateway/api/api_keys.py` — `POST /dashboard/api-keys` (201 with full key), `GET /dashboard/api-keys` (list masked)
  - [x] 4.3: Mount new routers in `gateway/api/router.py`

- [x] Task 5: Auth middleware (AC: #4, #5, #6)
  - [x] 5.1: Create `gateway/middleware/auth.py` — Bearer token extraction, Redis cache lookup, DB + argon2 verify on miss, 60s cache set, 401 on failure
  - [x] 5.2: Create `gateway/middleware/error_handler.py` — Global exception handler mapping `GatewayError` subclasses to HTTP responses with error envelope
  - [x] 5.3: Wire middleware into `gateway/main.py` lifespan (error handler as exception handler, not middleware class)

- [x] Task 6: Tests (AC: all)
  - [x] 6.1: Create `tests/api/test_auth.py` — test signup (201), duplicate email (409), login (200 + JWT), invalid password (401)
  - [x] 6.2: Create `tests/api/test_api_keys.py` — test key creation (201, full key returned once), key listing (masked), unauthenticated (401)
  - [x] 6.3: Create `tests/middleware/test_auth_middleware.py` — test valid key (cache hit), valid key (cache miss → DB), invalid key (401), missing header (401)
  - [x] 6.4: Create `tests/services/test_auth_service.py` — test password hashing, JWT create/verify
  - [x] 6.5: Create `tests/services/test_api_key_service.py` — test key generation format, argon2 hash stored not plaintext
  - [x] 6.6: Update `tests/conftest.py` — session-scoped DB cleanup, auth_headers fixture
  - [x] 6.7: Verify `uv run pytest` passes with all new tests (36/36)
  - [x] 6.8: Verify `uv run ruff check` and `uv run mypy gateway` pass with zero errors

## Dev Notes

### Architecture Compliance — CRITICAL

**DO NOT deviate from these patterns. They are load-bearing decisions from the Architecture document.**

#### Database Models

**`organizations` table** (`gateway/models/organization.py`):
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**IMPORTANT:** Define `Base` in a shared location (e.g., `gateway/models/base.py`) so all models use the same metadata. Alembic's `env.py` must import `Base.metadata` for autogenerate to work.

**`api_keys` table** (`gateway/models/api_key.py`):
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from gateway.models.base import Base

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)  # e.g. "tao_sk_live_abc123"
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # argon2 hash of full key
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Column naming follows architecture:** `snake_case`, plural table names, FK convention `{table_singular}_id`.

#### API Key Format & Generation

```
Full key:    tao_sk_live_<20 random url-safe chars>
             tao_sk_test_<20 random url-safe chars>
Prefix:      first 20 chars including environment marker, e.g. "tao_sk_live_a1b2c3d4"
             (stored plaintext in api_keys.prefix for identification/display)
key_hash:    argon2.hash(full_key)  — stored in api_keys.key_hash
```

Generation pattern (`gateway/services/api_key_service.py`):
```python
import secrets
from argon2 import PasswordHasher

ph = PasswordHasher()

def generate_api_key(env: str = "live") -> tuple[str, str, str]:
    """Returns (full_key, prefix, key_hash)"""
    random_suffix = secrets.token_urlsafe(20)
    full_key = f"tao_sk_{env}_{random_suffix}"
    prefix = full_key[:20]  # First 20 chars as prefix for display
    key_hash = ph.hash(full_key)
    return full_key, prefix, key_hash
```

**CRITICAL:** Return `full_key` to the user EXACTLY ONCE at creation time. Never store or log it.

#### Auth Service Pattern

```python
# gateway/services/auth_service.py
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError
from gateway.core.config import settings

ph = PasswordHasher()

async def signup(email: str, password: str, db: AsyncSession) -> Organization:
    password_hash = ph.hash(password)
    org = Organization(email=email, password_hash=password_hash)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org

async def login(email: str, password: str, db: AsyncSession) -> str:
    org = await db.scalar(select(Organization).where(Organization.email == email))
    if org is None:
        raise AuthenticationError("Invalid credentials")
    try:
        ph.verify(org.password_hash, password)
    except VerifyMismatchError:
        raise AuthenticationError("Invalid credentials")
    return create_jwt_token(str(org.id))

def create_jwt_token(org_id: str) -> str:
    payload = {
        "sub": org_id,
        "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_jwt_token(token: str) -> str:
    """Returns org_id string or raises AuthenticationError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except JWTError:
        raise AuthenticationError("Invalid or expired token")
```

**Use `argon2-cffi` — NOT passlib, NOT bcrypt.** The architecture explicitly calls out argon2-cffi.

#### Middleware Auth Pattern

```python
# gateway/middleware/auth.py
import structlog
from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()
logger = structlog.get_logger()
security = HTTPBearer()

async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> uuid.UUID:
    """FastAPI dependency — validates Bearer token, returns key ID."""
    token = credentials.credentials
    prefix = token[:20]  # Use first 20 chars as cache key
    cache_key = f"api_key:{prefix}"

    # Try Redis cache first
    cached = await redis.get(cache_key)
    if cached:
        return uuid.UUID(cached.decode())

    # Cache miss — look up in DB
    key_record = await db.scalar(
        select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.is_active == True)  # noqa: E712
    )
    if key_record is None:
        logger.warning("api_key_not_found", prefix=prefix[:12] + "****")
        raise AuthenticationError("Invalid API key")

    try:
        ph.verify(key_record.key_hash, token)
    except VerifyMismatchError:
        logger.warning("api_key_hash_mismatch", prefix=prefix[:12] + "****")
        raise AuthenticationError("Invalid API key")

    # Cache the result: prefix → key_id, 60s TTL
    await redis.set(cache_key, str(key_record.id), ex=60)
    return key_record.id
```

Use this as a `Depends()` on all protected routes: `key_id: uuid.UUID = Depends(get_current_api_key)`.

**NEVER log the full API key.** The structlog redaction processor handles it, but also be deliberate — only log `prefix[:12] + "****"`.

#### Error Handler Pattern

```python
# gateway/middleware/error_handler.py
from fastapi import Request
from fastapi.responses import JSONResponse
from gateway.core.exceptions import GatewayError

async def gateway_exception_handler(request: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.error_type,
                "message": exc.message,
                "code": exc.status_code,
            }
        },
    )
```

Register in `gateway/main.py`:
```python
from gateway.core.exceptions import GatewayError
from gateway.middleware.error_handler import gateway_exception_handler

app.add_exception_handler(GatewayError, gateway_exception_handler)  # type: ignore[arg-type]
```

The `# type: ignore[arg-type]` is needed because FastAPI's type signature for `add_exception_handler` expects `HTTPException`, but GatewayError is our custom base.

#### JWT in This Story

This story delivers **Bearer token auth for API requests only**. JWT is used for:
- Dashboard login → `POST /auth/login` returns JWT
- `POST /dashboard/api-keys` is protected by JWT (not by API key)

JWT stored as a simple response field (not httpOnly cookie yet — that's Epic 4 when the React dashboard exists). Return format:
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

The `Authorization: Bearer tao_sk_live_...` flow (Bearer API key) is separate from JWT and handled by the `get_current_api_key` dependency.

#### Pydantic Schemas

```python
# gateway/schemas/auth.py
from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str  # min_length=8 via Field(min_length=8)

class SignupResponse(BaseModel):
    id: str  # UUID as string
    email: str
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# gateway/schemas/api_keys.py
from pydantic import BaseModel
from datetime import datetime

class ApiKeyCreateRequest(BaseModel):
    environment: str = "live"  # "live" | "test"

class ApiKeyCreateResponse(BaseModel):
    id: str
    key: str           # Full key — shown once only
    prefix: str        # First 20 chars for display
    created_at: datetime

class ApiKeyListItem(BaseModel):
    id: str
    prefix: str        # Masked display — never full key
    is_active: bool
    created_at: datetime
```

#### Test Fixtures Pattern

Tests for this story require real database interaction. Use transaction rollback to isolate tests:

```python
# tests/conftest.py — additions to existing file
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

TEST_DATABASE_URL = "postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway_test"

@pytest.fixture(scope="session")
def engine():
    return create_async_engine(TEST_DATABASE_URL)

@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> dict[str, str]:
    """Creates an org, logs in, returns JWT auth headers."""
    # signup → login → return {"Authorization": "Bearer <jwt>"}
    ...
```

**Note:** Tests that exercise the auth middleware and API key validation need Redis available. Consider using `fakeredis` for unit tests and real Redis (from docker-compose) for integration tests.

#### Alembic Migration

After creating models, run:
```bash
uv run alembic revision --autogenerate -m "create organizations and api keys tables"
```

The generated migration should create both tables. Verify it looks correct before applying. Common issues:
- UUID columns need `postgresql.UUID` import from `sqlalchemy.dialects.postgresql`
- `server_default=func.now()` should appear as `server_default=sa.text("now()")` in migration

Apply:
```bash
uv run alembic upgrade head
```

Check migration target in `migrations/env.py` is using the async pattern established in Story 1.1.

#### Router Mounting

Update `gateway/api/router.py`:
```python
from gateway.api.auth import router as auth_router
from gateway.api.api_keys import router as api_keys_router

router = APIRouter()
router.include_router(health_router, tags=["Health"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(api_keys_router, prefix="/dashboard", tags=["API Keys"])
```

### Library & Framework Requirements

| Library | Why |
|---|---|
| `argon2-cffi` | Password and API key hashing — MANDATORY, not passlib |
| `python-jose[cryptography]` | JWT encode/decode |
| `sqlalchemy[asyncio]` + `asyncpg` | Async DB access — already installed |
| `redis[hiredis]` | 60s key cache — already installed |
| `pydantic[email]` | `EmailStr` validation for signup |

All libraries already installed from Story 1.1. No new dependencies needed.

### Project Structure Notes

New files to create:
```
gateway/
├── models/
│   ├── base.py           # DeclarativeBase (NEW — split out from organization.py)
│   ├── organization.py   # Organization model (NEW)
│   └── api_key.py        # ApiKey model (NEW)
├── schemas/
│   ├── auth.py           # Auth request/response schemas (NEW)
│   └── api_keys.py       # API key schemas (NEW)
├── api/
│   ├── auth.py           # /auth/signup, /auth/login (NEW)
│   └── api_keys.py       # /dashboard/api-keys (NEW)
├── services/
│   ├── auth_service.py   # signup, login, JWT (NEW)
│   └── api_key_service.py # generate, list, revoke (NEW)
└── middleware/
    ├── auth.py           # Bearer token validation (NEW)
    └── error_handler.py  # GatewayError → HTTP (NEW)

migrations/
└── versions/
    └── <hash>_create_organizations_and_api_keys_tables.py  # NEW

tests/
├── api/
│   ├── test_auth.py          # NEW
│   └── test_api_keys.py      # NEW
├── middleware/
│   └── test_auth_middleware.py  # NEW
└── services/
    ├── test_auth_service.py   # NEW
    └── test_api_key_service.py # NEW
```

Modified files:
- `gateway/models/__init__.py` — export Organization, ApiKey, Base
- `gateway/api/router.py` — mount auth + api_keys routers
- `gateway/main.py` — register exception handler
- `migrations/env.py` — import models for autogenerate
- `tests/conftest.py` — add db_session, auth_headers fixtures

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.2] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication-&-Security] — Auth decisions: argon2, JWT httpOnly cookies, bearer token
- [Source: _bmad-output/planning-artifacts/architecture.md#Core-Architectural-Decisions] — API key cache (Redis 60s TTL), NFR3 <10ms validation
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure-&-Boundaries] — File locations for models, schemas, api, middleware, services
- [Source: _bmad-output/planning-artifacts/architecture.md#Naming-Patterns] — Table naming (snake_case plural), FK convention (org_id), index naming
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation-Patterns-&-Consistency-Rules] — Logging patterns, Depends() injection, async patterns
- [Source: _bmad-output/planning-artifacts/prd.md#FR1] — Account creation with email/password
- [Source: _bmad-output/planning-artifacts/prd.md#FR4] — API key generation with environment prefixes
- [Source: _bmad-output/planning-artifacts/prd.md#FR31] — Bearer token auth on all API requests
- [Source: _bmad-output/planning-artifacts/prd.md#FR32] — Keys hashed one-way, never plaintext
- [Source: _bmad-output/planning-artifacts/prd.md#NFR3] — <10ms key validation via cache

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References
- Fixed ruff B008 false positive: added `B008` to `[tool.ruff.lint] ignore` since `Depends()` in function defaults is standard FastAPI pattern
- Fixed ruff B904: all `except` clauses now use `raise ... from exc` or `raise ... from None`
- Fixed ruff UP017: replaced `timezone.utc` with `datetime.UTC` alias (Python 3.12+)
- Fixed mypy `jose.*` missing stubs: added `jose.*` to mypy overrides `ignore_missing_imports`
- Fixed mypy `no-any-return` on `jwt.encode`: explicit `token: str` annotation
- Fixed pytest-asyncio event loop conflicts: set `asyncio_default_test_loop_scope = "session"` to share a single event loop across all async tests, preventing asyncpg connection pool corruption between tests

### Completion Notes List
- All 6 tasks completed (28 subtasks)
- 36 tests pass (7 auth, 4 api-key, 4 middleware, 4 auth-service, 5 api-key-service, 9 model, 3 health)
- `uv run ruff check gateway/ tests/` — all checks passed
- `uv run mypy gateway/` — no issues found in 31 source files
- `uv run pytest` — 36/36 pass in ~1s, idempotent across runs
- Alembic migration 795f9c954fcb creates `organizations` and `api_keys` tables with proper indexes and FK constraints
- All auth patterns follow architecture exactly: argon2-cffi (not passlib), python-jose JWT, Redis 60s TTL cache, `Depends()` injection
- Error handler registered via `app.add_exception_handler(GatewayError, ...)` with standard error envelope
- No new dependencies added — all libraries already installed from Story 1.1

### Change Log
- 2026-03-12: Story 1.2 implementation — DB models, auth service, API key service, auth middleware, error handler, API routes, 36 tests
- 2026-03-12: Adversarial code review — fixed 3 HIGH (timing attack, no rate limiting, tests on prod DB) + 3 MEDIUM (false File List claim, unsafe fixture, no per-test isolation). 40/40 tests pass.
- 2026-03-12: Second adversarial code review — fixed 2 HIGH (revoked key cache invalidation, password max_length DoS) + 4 MEDIUM (rate limit race condition, JWT UUID validation, env type constraint, rate limit test coverage). 42/42 tests pass.
- 2026-03-12: Third adversarial code review — fixed 1 HIGH (rate limit broken behind proxy, is_active missing server_default) + 3 MEDIUM (email PII logged, LoginRequest min_length, test fixture DB cleanup). 42/42 tests pass.
- 2026-03-12: Fourth adversarial code review — fixed 2 HIGH (redis.keys O(N) in tests, trusted proxy validation) + 2 MEDIUM (revoke cache race condition, duplicate conftest cleanup). 42/42 tests pass.
- 2026-03-12: Fifth adversarial code review — fixed 2 HIGH (missing updated_at audit trail on models, hand-written Alembic migration ID) + 3 MEDIUM (rate limit sliding window → fixed window via Lua, argon2 rehash check on login+key verify, get_current_api_key returns ApiKeyInfo with org_id). JWT now includes iat claim. 43/43 tests pass.
- 2026-03-12: Sixth adversarial code review — fixed 1 HIGH (revoke_api_key cache delete before DB commit) + 3 MEDIUM (no pagination on list_api_keys, cache corruption returns 500 instead of DB fallback, rehash commit failure kills valid request). 43/43 tests pass.
- 2026-03-12: Seventh adversarial code review (combined 1.1+1.2) — fixed 3 HIGH (missing revoke endpoint, revoke cache race TOCTOU, no pagination bounds) + 2 HIGH (no per-org key limit, signup IntegrityError session state) + 2 MEDIUM (prefix magic number, test Redis cleanup O(N)). Added revoke endpoint, pagination validation, per-org key limit, expired JWT test, revoke tests. 49/49 tests pass.

### File List
- gateway/models/base.py (new) — DeclarativeBase shared by all models
- gateway/models/organization.py (new) — Organization model with organizations table
- gateway/models/api_key.py (new) — ApiKey model with api_keys table
- gateway/models/__init__.py (modified) — exports Base, Organization, ApiKey
- gateway/schemas/auth.py (new) — SignupRequest/Response, LoginRequest/Response
- gateway/schemas/api_keys.py (new) — ApiKeyCreateRequest/Response, ApiKeyListItem
- gateway/services/auth_service.py (new) — signup, login, JWT create/verify
- gateway/services/api_key_service.py (new) — generate, create, list, revoke API keys
- gateway/api/auth.py (new) — POST /auth/signup, POST /auth/login
- gateway/api/api_keys.py (new) — POST /dashboard/api-keys, GET /dashboard/api-keys
- gateway/api/router.py (modified) — mount auth + api_keys routers
- gateway/middleware/auth.py (new) — get_current_api_key, get_current_org_id dependencies
- gateway/middleware/error_handler.py (new) — GatewayError → JSON error envelope
- gateway/main.py (modified) — register exception handler
- migrations/env.py (modified) — import Base.metadata for autogenerate
- migrations/versions/795f9c954fcb_create_organizations_and_api_keys_tables.py (new)
- ~~pyproject.toml~~ (REMOVED — these settings already existed from Story 1.1, not modified in this story)
- tests/conftest.py (modified) — session-scoped DB cleanup, jwt_token + auth_headers fixtures
- tests/api/test_auth.py (new) — 7 auth endpoint tests
- tests/api/test_api_keys.py (new) — 4 API key endpoint tests
- tests/middleware/test_auth_middleware.py (new) — 4 middleware tests
- tests/services/__init__.py (new)
- tests/services/test_auth_service.py (new) — 4 service tests
- tests/services/test_api_key_service.py (new) — 5 service tests
- tests/models/__init__.py (new)
- tests/models/test_models.py (new) — 9 model structure tests

**Code Review Fixes (2026-03-12):**
- gateway/core/security.py (new) — shared PasswordHasher instance (was duplicated in 3 modules)
- gateway/core/config.py (modified) — warns on startup if jwt_secret_key is the insecure default
- gateway/schemas/api_keys.py (modified) — `environment` field validated as `Literal["live", "test"]`
- gateway/services/auth_service.py (modified) — use shared ph from gateway.core.security
- gateway/services/api_key_service.py (modified) — use shared ph from gateway.core.security
- gateway/middleware/auth.py (modified) — use shared ph from gateway.core.security
- tests/middleware/test_auth_middleware.py (modified) — added 5 unit tests covering cache hit, cache miss, invalid hash, key not found, missing credentials
- tests/api/test_api_keys.py (modified) — fixed dead assertion in test_list_api_keys_masked

**Adversarial Code Review Fixes (2026-03-12):**
- gateway/services/auth_service.py (modified) — constant-time login rejection via dummy argon2 hash to prevent email enumeration timing attacks
- gateway/api/auth.py (modified) — added per-IP Redis rate limiting (30/min) on auth endpoints to prevent brute force
- gateway/core/config.py (modified) — added auth_rate_limit_per_minute setting
- tests/conftest.py (modified) — tests now use tao_gateway_test database (not production), per-test DB truncation + Redis rate limit key cleanup for full isolation

**Third Adversarial Code Review Fixes (2026-03-12):**
- gateway/main.py (modified) — added SQLAlchemy engine disposal on shutdown
- gateway/api/auth.py (modified) — rate limit uses X-Forwarded-For for real client IP behind proxy; removed email PII from log
- gateway/models/api_key.py (modified) — added server_default=true to is_active column
- gateway/schemas/auth.py (modified) — added min_length=8 to LoginRequest.password
- docker-compose.yml (modified) — healthcheck uses configurable POSTGRES_USER
- tests/conftest.py (modified) — DB truncation + api_key cache cleanup before and after each test
- migrations/versions/a1b2c3d4e5f6_add_is_active_server_default.py (new) — adds server_default to is_active column

**Second Adversarial Code Review Fixes (2026-03-12):**
- gateway/schemas/auth.py (modified) — added max_length=128 on SignupRequest and LoginRequest password fields to prevent argon2 DoS
- gateway/services/api_key_service.py (modified) — revoke_api_key now invalidates Redis cache; env param typed as Literal["live", "test"]
- gateway/api/auth.py (modified) — rate limit uses Redis pipeline for atomic incr+expire (no TTL-less key on crash)
- gateway/middleware/auth.py (modified) — get_current_org_id catches ValueError on invalid UUID in JWT sub claim, returns 401
- tests/api/test_auth.py (modified) — added test_signup_password_too_long_returns_422 and test_rate_limit_blocks_after_threshold

**Fifth Adversarial Code Review Fixes (2026-03-12):**
- gateway/models/organization.py (modified) — added updated_at column with server_default and onupdate
- gateway/models/api_key.py (modified) — added updated_at column with server_default and onupdate
- gateway/api/health.py (modified) — added 5s in-memory response cache to prevent DDoS via external calls
- gateway/api/auth.py (modified) — replaced pipeline INCR+EXPIRE with Lua script for true fixed-window rate limit
- gateway/core/redis.py (modified) — added max_connections=20 to Redis connection pool
- gateway/middleware/auth.py (modified) — added ApiKeyInfo dataclass returning both key_id and org_id; added argon2 rehash check
- gateway/services/auth_service.py (modified) — added argon2 rehash check on login; added iat claim to JWT
- migrations/versions/6873921e4697_add_is_active_default_and_updated_at.py (new) — replaces hand-written a1b2c3d4e5f6 migration; adds updated_at to both tables
- (deleted) migrations/versions/a1b2c3d4e5f6_add_is_active_server_default.py — replaced with properly ID'd migration
- tests/conftest.py (modified) — session-scoped drop/create_all for auto table setup; dynamic table names for TRUNCATE; health cache clearing
- tests/middleware/test_auth_middleware.py (modified) — updated for ApiKeyInfo return type with org_id
- tests/services/test_auth_service.py (modified) — added test_jwt_contains_iat_claim
- tests/models/test_models.py (modified) — updated column assertions to include updated_at

**Sixth Adversarial Code Review Fixes (2026-03-12):**
- docker-compose.yml (modified) — added DEBUG and JWT_SECRET_KEY env vars so fresh clone starts successfully
- gateway/services/api_key_service.py (modified) — revoke commits DB before deleting Redis cache; list_api_keys has pagination (limit/offset)
- gateway/api/api_keys.py (modified) — list endpoint accepts limit/offset query params
- gateway/middleware/auth.py (modified) — cache hit handles corrupt data gracefully; rehash failure doesn't kill valid request
- gateway/services/auth_service.py (modified) — login rehash failure doesn't kill valid login
