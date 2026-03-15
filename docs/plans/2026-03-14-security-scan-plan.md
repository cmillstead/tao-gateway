# Security Scan Remediation Plan — 2026-03-14

**Scan**: tao-gateway Security Scan 2026-03-14
**Findings**: 0 CRIT, 5 HIGH, 7 MED, 8 LOW (20 total)
**Vault**: `tao-gateway Security Scan 2026-03-14.md`

## Priority 1: HIGH findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| SEC-003 | Validation error handler leaks raw input (passwords) | Small | DONE |
| SEC-004 | GitHub Actions not SHA-pinned (supply chain) | Small | DONE |
| SEC-005 | No dependency vulnerability scanning in CI | Small | DONE |
| SEC-001 | Rate limiting fails open when Redis down | Medium | DONE |
| SEC-002 | Argon2 hash stored in Redis cache | Medium | DONE |

## Priority 2: MEDIUM findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| SEC-006 | Refresh token race condition | Medium | DONE |
| SEC-007 | Trusted proxy rate limit bypass | Small | ACCEPTED — XFF logic is correct; documented constraint |
| SEC-008 | CSP header mismatch | Medium | DONE |
| SEC-009 | Admin /developers exposes all emails | Small | DONE |
| SEC-010 | Admin /miners exposes full hotkeys | Small | DONE |
| SEC-011 | Debug log content unredacted | Medium | DONE |
| SEC-012 | Python deps unpinned | Small | DONE |

## Priority 3: LOW findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| SEC-013 | Deploy SSH key risk (chains with SEC-004) | Small | DONE (via SEC-004 SHA pinning) |
| SEC-014 | /v1/models unauthenticated | Trivial | ACCEPTED — OpenAI convention |
| SEC-015 | Refresh token cookie over-scoped | Small | DONE |
| SEC-016 | Redis keys expose API key prefixes | Small | DONE |
| SEC-017 | SPA serves source maps | Small | DONE |
| SEC-018 | Bittensor massive dep surface | N/A | Monitor |
| SEC-019 | Unpinned dev dependencies | Small | DONE |
| SEC-020 | curl in Docker container | Small | DONE |

## Summary

- **Fixed**: 17/20 findings
- **Accepted**: 2 (SEC-007 trusted proxy — correct logic; SEC-014 /v1/models — by design)
- **Monitor**: 1 (SEC-018 bittensor dep surface — inherent to SDK)
- All 578 tests pass, ruff clean, mypy clean, Docker builds
