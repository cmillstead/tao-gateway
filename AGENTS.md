# Tao Gateway — Agent Navigation

FastAPI gateway for Bittensor. Python 3.12, async SQLAlchemy, Redis, JWT auth.

## Quick Reference

- **Full details**: See `CLAUDE.md` for tech stack, testing rules

## 1. Environment — Check Before Starting

- **Repository state**: `git status`, `git stash list`, `git branch`
- **CI/PR state**: `gh run list --limit 5`, `gh pr list`, `gh pr view`
- **Recent history**: `git log --oneline -20`
- **Escalation**: If CI is already failing on an unrelated issue, note it and proceed

## 2. Memory — Check Prior Knowledge

- **Git memory**: `git log --oneline -- <file>`, `git blame -L <start>,<end> <file>`
- **QMD vault**: Use QMD `search` and `vector_search` tools. QMD indexes `~/src/**/*.md`
- **ContextKeep**: `list_all_memories`, `retrieve_memory` (when configured, skip if unavailable)
- **Escalation**: If Memory reveals a prior decision that contradicts the current task, surface to user

## 3. Task — Assemble Context for the Work

- **Find code**: Use Grep/Glob to find functions and classes before modifying them
- Read specific functions, not whole files
- Read test files for modules you'll change
- Check prior analysis: scan reports and plans in `docs/plans/`
- Don't pre-load — load incrementally

## Commands

```bash
uv run pytest --tb=short -q       # Run tests
uv run ruff check gateway/ tests/ # Lint
uv run mypy gateway/              # Type check
```

## Key Rules

- Use real Postgres and Redis (Docker test containers) over mocks
- Only mock external services impractical to run locally (e.g., Bittensor SDK)
- Package manager: uv
- Auth: argon2 for API key hashing, JWT for dashboard
- Logging: structlog

## 4. Validation — Before Claiming Done

- **Self-review**: `git diff --stat`, `git diff`, re-read task/issue for acceptance criteria
- **Local verification**: `uv run pytest --tb=short -q && uv run ruff check gateway/ tests/ && uv run mypy gateway/`
- **After pushing**: `gh run list --limit 1`, `gh run view <id>`, fix CI failures immediately
- **Common CI failures**: type errors, ruff formatting
- **Don't claim done until**: local tests pass, CI green, diff is intentional only


## Boundaries

### Always Do
- Run tests and linting before committing — NEVER commit without verification
- Follow the architectural layer structure defined above
- Use real implementations in tests — NEVER use mocks, patches, or stubs
- Use existing utilities before creating new ones — search before writing
- Write tests alongside new code — NEVER ship untested business logic
- Read the spec/plan before implementing — understand "done" before starting

### Ask First
- Adding a new external dependency
- Modifying database schema or migrations
- Changing public API contracts or interfaces
- Deleting or moving files in shared directories
- Any change affecting more than 3 modules

### Never Do
- NEVER commit secrets, tokens, API keys, or credentials
- NEVER modify deployed migration files
- NEVER skip or disable tests to make CI pass
- NEVER force push to main or release branches
- NEVER commit .env files or sensitive configuration
- NEVER introduce a new framework or library without explicit approval
- NEVER claim work is done without running verification
- NEVER retry the same failed approach more than 3 times — escalate instead
- NEVER expand task scope without asking — park new ideas separately

## Golden Principles
Read docs/golden-principles.md when: making architectural decisions, resolving ambiguity, or unsure which approach to take.
