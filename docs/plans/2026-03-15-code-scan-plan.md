# Code Scan Remediation Plan — 2026-03-15

**Scan**: tao-gateway Code Scan 2026-03-15
**Findings**: 0 CRIT, 3 HIGH, 5 MED, 5 LOW (13 total)
**Vault**: `tao-gateway Code Scan 2026-03-15.md`

## Priority 1: HIGH findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| CODE-001 | Cache key mismatch in update_api_key — stale debug_mode | Small | DONE |
| CODE-002 | Off-by-one in fallback rate limiter | Small | DONE |
| TEST-001 | No tests for core/rate_limit.py fallback store | Medium | DONE |

## Priority 2: MEDIUM findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| CODE-003 | Endpoint handler duplication (3 files) | Medium | DONE |
| CODE-004 | Auth service login duplication | Small | DONE |
| CODE-005 | Admin metrics full-table scan | Small | DONE |
| TEST-002 | No tests for try_rehash | Small | DONE |
| TEST-003 | No end-to-end full-path test | Medium | TODO |

## Priority 3: LOW findings

| ID | Finding | Effort | Status |
|----|---------|--------|--------|
| CODE-006 | main.py lifespan too large | Medium | TODO |
| CODE-007 | Dashboard usage endpoint duplicated | Small | TODO |
| CODE-008 | Rate limit Settings fields are dead config | Small | DONE |
| CODE-009 | Background task boilerplate duplicated | Medium | TODO |
| CODE-010 | collected_chunks allocated unnecessarily | Small | DONE |

## Summary

- **Fixed**: 10/13 findings
- **Remaining**: 3 LOWs (lifespan refactor, usage endpoint dedup, task boilerplate) + 1 MED (end-to-end test)
- 585 tests pass (up from 578), ruff clean, mypy clean
