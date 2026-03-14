# Security Scan Remediation Plan — 2026-03-13

## Source
Security scan performed 2026-03-13. Full report: `~/Documents/obsidian-vault/AI/context/goals/projects/tao-gateway-security-scan-2026-03-13.md`

## Findings: 22 total (2 CRIT, 6 HIGH, 8 MED, 6 LOW)

---

## P0 — Must Fix Immediately

### Step 1: Replace python-jose with PyJWT (SEC-001) [CRIT]
- [ ] `uv remove python-jose`
- [ ] `uv add pyjwt[crypto]`
- [ ] Update `gateway/services/auth_service.py`:
  - Change `from jose import JWTError, jwt` to `import jwt` and `from jwt.exceptions import PyJWTError`
  - Update `jwt.encode()` — PyJWT returns `str` directly (no need to cast)
  - Update `jwt.decode()` — same API, catch `PyJWTError` instead of `JWTError`
- [ ] Update `pyproject.toml` mypy overrides (remove `jose.*`, add `jwt.*` if needed)
- [ ] Run tests, verify JWT auth still works
- [ ] Verify `ecdsa` package removed from `uv.lock`

### Step 2: Fix docker-compose defaults (SEC-002) [CRIT]
- [ ] Change `DEBUG=${DEBUG:-true}` to `DEBUG=${DEBUG:-false}` in docker-compose.yml
- [ ] Remove default value for JWT_SECRET_KEY (require explicit setting)
- [ ] Verify `docker-compose up` without .env fails with clear error message

---

## P1 — Fix Before Next Release

### Step 3: Replace regex sanitization with nh3 (SEC-003, SEC-004)
- [ ] `uv add nh3`
- [ ] Replace `BaseAdapter.sanitize_text()` body with `nh3.clean(text, tags=set())`
- [ ] Remove regex class attributes (`_DANGEROUS_TAGS_RE`, etc.) or keep as defense-in-depth
- [ ] Update tests: add bypass payloads as test cases
- [ ] Streaming is automatically fixed since `sanitize_text` is called per-chunk

### Step 4: Add request body size limit + content max_length (SEC-006, SEC-022)
- [ ] Add `max_length=100_000` to `ChatMessage.content` in `schemas/chat.py`
- [ ] Add `max_length=64` to `ChatCompletionRequest.model`
- [ ] Add `max_length=100` to `ChatCompletionRequest.messages` list
- [ ] Add body size limit middleware in `main.py` (check Content-Length, return 413 if >1MB)
- [ ] Add tests for oversized payloads

### Step 5: Fix SQLAlchemy echo in debug mode (SEC-007)
- [ ] Change `echo=settings.debug` to `echo=False` in `database.py`
- [ ] If SQL debugging is needed, document using `SQLALCHEMY_ECHO=true` env var separately from DEBUG

---

## P2 — Fix Soon

### Step 6: Add per-key chat rate limiting (SEC-005)
- [ ] Create rate limiting middleware for chat endpoint (similar to auth rate limiter)
- [ ] Key on `api_key.key_id`, configurable limit (e.g., 60 req/min)
- [ ] Fail open if Redis unavailable (consistent with auth rate limiter)
- [ ] Add tests

### Step 7: Add SSRF protection for miner IPs (SEC-008)
- [ ] In `MinerSelector.select_miner()` or `BaseAdapter.execute()`, validate `axon.ip`:
  - Reject private ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
  - Reject loopback: 127.0.0.0/8
  - Reject link-local: 169.254.0.0/16
  - Reject metadata: 169.254.169.254
- [ ] Log rejected miners, skip to next eligible
- [ ] Add tests with private IPs

### Step 8: Sanitize SSE error messages (SEC-009)
- [ ] In `base.py` _stream_generator, replace `str(exc)` with generic messages:
  - Line 269: `"Miner communication error"`
  - Line 315: `"Miner communication error"`
- [ ] Keep `str(exc)` in the `logger.warning()` calls (server-side only)

### Step 9: Fallback rate limiter + health endpoint hardening (SEC-010)
- [ ] Add in-memory fallback rate limiter for auth endpoints when Redis is unavailable
- [ ] Consider splitting health endpoint: public (status only) vs authenticated (full details)

---

## P3 — Backlog

- [ ] SEC-011: Add CORS middleware with restrictive origins
- [ ] SEC-012: Fix Redis URL logging redaction
- [ ] SEC-013: Add Redis AUTH in docker-compose
- [ ] SEC-014: Genericize signup response for existing emails
- [ ] SEC-015: Document wallet encryption requirement
- [ ] SEC-016: Add missing redaction patterns (email, database_url, redis_url, wallet_path)
- [ ] SEC-017: Add iss/aud claims to JWT
- [ ] SEC-018: Remove miner_uid from client-facing error responses
- [ ] SEC-019: Add client_ip to redaction patterns
- [ ] SEC-020: Pin Dockerfile base image to digest
- [ ] SEC-021: Bind gateway port to 127.0.0.1 in dev compose
