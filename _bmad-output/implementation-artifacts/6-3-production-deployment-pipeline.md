# Story 6.3: Production Deployment Pipeline

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want a CI/CD pipeline and production deployment configuration,
so that code changes are automatically tested and deployed to the live gateway with zero-downtime.

## Acceptance Criteria

1. **Given** a push to any branch or a pull request
   **When** the GitHub Actions CI workflow runs
   **Then** it executes: `ruff check`, `mypy`, `pytest` with coverage
   **And** the dashboard builds successfully (`npm run build`)
   **And** the workflow fails fast on any check failure

2. **Given** a merge to the `main` branch
   **When** the GitHub Actions deploy workflow runs
   **Then** it builds the Docker image, pushes to a container registry, and deploys to the DigitalOcean Droplet via SSH
   **And** the deployment uses `docker-compose.prod.yml` (gateway + Redis, managed Postgres external)

3. **Given** the production Droplet
   **When** the Caddy reverse proxy is configured
   **Then** it auto-provisions TLS via Let's Encrypt for the gateway domain
   **And** proxies HTTPS traffic to the FastAPI container
   **And** the Caddyfile is version-controlled (already exists, ~26 lines)

4. **Given** the production environment
   **When** the gateway starts
   **Then** it loads secrets from host environment variables (not .env files)
   **And** the wallet directory is mounted as a Docker volume with 700 permissions
   **And** structlog outputs JSON for log aggregation

5. **Given** the deployment pipeline
   **When** a deployment completes
   **Then** the `/v1/health` endpoint confirms the new version is running
   **And** zero-downtime deployment is achieved via container restart with health check

## Tasks / Subtasks

- [ ] Task 1: Create GitHub Actions CI workflow (AC: #1)
  - [ ] 1.1 Create `.github/workflows/ci.yml` — triggers on push to any branch and pull_request events
  - [ ] 1.2 Job: `lint` — runs `uv run ruff check gateway/ tests/` and `uv run mypy gateway/`
  - [ ] 1.3 Job: `test` — starts Postgres and Redis services, runs `uv run pytest --tb=short -q` with coverage
  - [ ] 1.4 Job: `dashboard-build` — runs `cd dashboard && npm ci && npm run build`
  - [ ] 1.5 Use `astral-sh/setup-uv@v5` for uv installation, `actions/setup-node@v4` with Node 20 for dashboard
  - [ ] 1.6 Python 3.12 via `actions/setup-python@v5`
  - [ ] 1.7 Cache uv dependencies and npm dependencies for faster runs
  - [ ] 1.8 Fail fast on any check failure (default GitHub Actions behavior)

- [ ] Task 2: Create GitHub Actions deploy workflow (AC: #2, #5)
  - [ ] 2.1 Create `.github/workflows/deploy.yml` — triggers on push to `main` only
  - [ ] 2.2 Step: Build Docker image with `docker build -t ghcr.io/<owner>/tao-gateway:latest -t ghcr.io/<owner>/tao-gateway:${{ github.sha }} .`
  - [ ] 2.3 Step: Log in to GitHub Container Registry using `docker/login-action@v3` with `GITHUB_TOKEN`
  - [ ] 2.4 Step: Push image to GHCR
  - [ ] 2.5 Step: SSH into Droplet using `appleboy/ssh-action@v1` with secrets (`DROPLET_HOST`, `DROPLET_SSH_KEY`, `DROPLET_USER`)
  - [ ] 2.6 SSH commands: pull new image, run `docker compose -f docker-compose.prod.yml up -d --force-recreate gateway`, run Alembic migrations, verify health endpoint
  - [ ] 2.7 Add health check verification: `curl -sf http://localhost:8000/v1/health` after deployment
  - [ ] 2.8 Deploy workflow should depend on CI passing (use `needs: ci` or run CI checks inline)

- [ ] Task 3: Create `docker-compose.prod.yml` (AC: #2, #4)
  - [ ] 3.1 Create `docker-compose.prod.yml` with `gateway` and `redis` services only (managed Postgres is external)
  - [ ] 3.2 Gateway service: pull image from GHCR, env vars from host (DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, WALLET_PATH, ENABLE_BITTENSOR=true), mount wallet volume with `:ro`, restart policy `unless-stopped`
  - [ ] 3.3 Redis service: `redis:7-alpine` with password auth, persistent volume, restart policy `unless-stopped`
  - [ ] 3.4 Gateway depends on Redis health check
  - [ ] 3.5 No `.env` file in production — all secrets from host environment variables
  - [ ] 3.6 Wallet volume mount with restrictive permissions: `${WALLET_PATH}:/app/.bittensor/wallets:ro`

- [ ] Task 4: Update Caddyfile for production domain (AC: #3)
  - [ ] 4.1 The Caddyfile already exists with security headers, TLS 1.2+, and reverse proxy config
  - [ ] 4.2 Replace `your-domain.com` placeholder with `{$DOMAIN:your-domain.com}` env var pattern so it's configurable
  - [ ] 4.3 Verify Caddy config includes: auto-TLS (Let's Encrypt), TLS 1.2+ enforcement, security headers, reverse proxy to localhost:8000
  - [ ] 4.4 NOTE: Caddy runs directly on the host (not in Docker) for port 80/443 binding — it reverse-proxies to the Docker-exposed gateway port

- [ ] Task 5: Create production environment documentation (AC: #4)
  - [ ] 5.1 Update `.env.example` to include all production-relevant env vars with clear comments distinguishing local-dev vs production values
  - [ ] 5.2 Add `REDIS_PASSWORD` to `.env.example` if not present
  - [ ] 5.3 Ensure `ENABLE_BITTENSOR=true` is documented for production
  - [ ] 5.4 Add `LOG_FORMAT=json` setting to `gateway/core/config.py` (default: `"console"`, production: `"json"`) and configure structlog to output JSON when `LOG_FORMAT=json`

- [ ] Task 6: Add structured JSON logging for production (AC: #4)
  - [ ] 6.1 Add `log_format: str = "console"` to `Settings` in `gateway/core/config.py`
  - [ ] 6.2 Update structlog configuration in `gateway/core/logging.py` to use `structlog.processors.JSONRenderer()` when `log_format == "json"` and `structlog.dev.ConsoleRenderer()` when `"console"`
  - [ ] 6.3 Add `LOG_FORMAT` to `.env.example` with comment: `# Set to "json" for production log aggregation`

- [ ] Task 7: Add Alembic migration to deploy workflow (AC: #2)
  - [ ] 7.1 In the deploy SSH script, run `docker compose -f docker-compose.prod.yml exec gateway .venv/bin/alembic upgrade head` after the new container is running
  - [ ] 7.2 This runs migrations inside the container using the production DATABASE_URL

- [ ] Task 8: Verify and test (AC: all)
  - [ ] 8.1 Verify CI workflow YAML is valid: use `actionlint` or manual review of workflow syntax
  - [ ] 8.2 Verify `docker-compose.prod.yml` is valid: `docker compose -f docker-compose.prod.yml config`
  - [ ] 8.3 Verify Dockerfile builds successfully: `docker build -t tao-gateway:test .`
  - [ ] 8.4 Verify all existing tests pass: `uv run pytest --tb=short -q`
  - [ ] 8.5 Verify linter: `uv run ruff check gateway/ tests/`
  - [ ] 8.6 Verify types: `uv run mypy gateway/`
  - [ ] 8.7 Verify dashboard builds: `cd dashboard && npm run build`

## Dev Notes

### Architecture Patterns and Constraints

- **Infrastructure-focused story** — creates CI/CD pipelines and production deployment config. Minimal application code changes (only structured logging config).
- **Existing infrastructure assets** — Dockerfile, docker-compose.yml (local dev), Caddyfile, and .env.example already exist. This story adds the production variants and CI/CD automation.
- **DigitalOcean Droplet** — single-server deployment. No Kubernetes. Docker Compose on the host.
- **Managed Postgres** — database is external (DO Managed Postgres, $15/mo). Not in docker-compose.prod.yml.
- **GHCR** (GitHub Container Registry) — free for public repos. Images pushed as `ghcr.io/<owner>/tao-gateway:<tag>`.
- **Caddy on host** — runs natively on the Droplet (not containerized) for port 80/443 binding and Let's Encrypt cert management. Reverse-proxies to the gateway container.
- **pydantic-settings** — loads env vars with priority over .env file. In production, no .env file — all config from host environment variables.
- **Zero-downtime deployment** — achieved via Docker health checks. `docker compose up -d --force-recreate gateway` starts new container, health check passes, old container removed.
- **Alembic migrations** — run after container is up, before the old container is fully removed.

### Current State — What Exists

| Component | Status | Location |
|---|---|---|
| Dockerfile (multi-stage, uv-based) | EXISTS | `Dockerfile` |
| docker-compose.yml (local dev) | EXISTS | `docker-compose.yml` |
| Caddyfile (security headers, TLS, reverse proxy) | EXISTS, placeholder domain | `Caddyfile` |
| .env.example | EXISTS | `.env.example` |
| Health endpoint `/v1/health` | EXISTS | `gateway/api/health.py` |
| Docker HEALTHCHECK | EXISTS in Dockerfile | `Dockerfile:29-30` |
| structlog configuration | EXISTS | `gateway/core/logging.py` |
| pydantic-settings config | EXISTS | `gateway/core/config.py` |
| `.github/workflows/` directory | DOES NOT EXIST | — |
| `ci.yml` | DOES NOT EXIST | — |
| `deploy.yml` | DOES NOT EXIST | — |
| `docker-compose.prod.yml` | DOES NOT EXIST | — |
| JSON log format support | DOES NOT EXIST | — |

### Existing Code to Leverage — DO NOT REINVENT

- **`Dockerfile`** — already has multi-stage build, non-root user, healthcheck, uv-based dependency install. DO NOT rewrite — use as-is for CI/CD image builds.
- **`docker-compose.yml`** — REFERENCE for production compose file. Production version drops Postgres (external), keeps Redis, uses image instead of build context.
- **`Caddyfile`** — already has security headers, TLS config, reverse proxy. Only needs domain placeholder update.
- **`.env.example`** — EXTEND with production-specific vars and LOG_FORMAT.
- **`gateway/core/config.py`** — ADD `log_format` setting here. Follow existing pattern of Field defaults.
- **`gateway/core/logging.py`** — MODIFY structlog setup to switch renderer based on `log_format` setting.
- **`gateway/api/health.py`** — health endpoint already exists, used by Docker HEALTHCHECK and deployment verification.

### What NOT to Touch

- Do NOT modify the existing Dockerfile (it's production-ready as-is)
- Do NOT modify docker-compose.yml (local dev config stays unchanged)
- Do NOT modify any application code except logging configuration
- Do NOT add Kubernetes, Helm, or container orchestration — single Droplet deployment
- Do NOT add monitoring/alerting infrastructure (Prometheus, Grafana) — Phase 2
- Do NOT modify existing tests or test infrastructure
- Do NOT add email notifications for deploy failures — GitHub Actions handles notifications natively
- Do NOT embed secrets in workflow files — use GitHub Secrets

### GitHub Actions CI Workflow Design

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: uv sync --frozen
      - run: uv run ruff check gateway/ tests/
      - run: uv run mypy gateway/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: tao
          POSTGRES_PASSWORD: tao
          POSTGRES_DB: tao_gateway_test
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U tao"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://tao:tao@localhost:5432/tao_gateway_test
      REDIS_URL: redis://localhost:6379/0
      JWT_SECRET_KEY: test-secret-key-for-ci-only-not-production
      DEBUG: 'true'
      ENABLE_BITTENSOR: 'false'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: uv sync --frozen
      - run: uv run pytest --tb=short -q

  dashboard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: dashboard/package-lock.json
      - run: cd dashboard && npm ci && npm run build
```

### GitHub Actions Deploy Workflow Design

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  ci:
    uses: ./.github/workflows/ci.yml  # Reuse CI workflow

  deploy:
    needs: ci
    runs-on: ubuntu-latest
    permissions:
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        run: |
          IMAGE=ghcr.io/${{ github.repository_owner }}/tao-gateway
          docker build -t $IMAGE:latest -t $IMAGE:${{ github.sha }} .
          docker push $IMAGE:latest
          docker push $IMAGE:${{ github.sha }}

      - name: Deploy to Droplet
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DROPLET_HOST }}
          username: ${{ secrets.DROPLET_USER }}
          key: ${{ secrets.DROPLET_SSH_KEY }}
          script: |
            cd /opt/tao-gateway
            docker pull ghcr.io/${{ github.repository_owner }}/tao-gateway:latest
            docker compose -f docker-compose.prod.yml up -d --force-recreate gateway
            sleep 5
            docker compose -f docker-compose.prod.yml exec gateway .venv/bin/alembic upgrade head
            curl -sf http://localhost:8000/v1/health || exit 1
            echo "Deployment successful"
```

### Production docker-compose.prod.yml Design

```yaml
services:
  gateway:
    image: ghcr.io/<owner>/tao-gateway:latest
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENABLE_BITTENSOR=${ENABLE_BITTENSOR:-true}
      - WALLET_PATH=/app/.bittensor/wallets
      - LOG_FORMAT=json
      - DEBUG=false
    volumes:
      - ${WALLET_PATH:-/root/.bittensor/wallets}:/app/.bittensor/wallets:ro
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  redis-data:
```

### Structured JSON Logging Design

Add to `gateway/core/config.py`:
```python
log_format: str = "console"  # "console" for local dev, "json" for production
```

Update `gateway/core/logging.py` to conditionally set the renderer:
```python
from gateway.core.config import settings

renderer = (
    structlog.processors.JSONRenderer()
    if settings.log_format == "json"
    else structlog.dev.ConsoleRenderer()
)
```

### GitHub Secrets Required

The deploy workflow requires these secrets configured in the GitHub repo:

| Secret | Description |
|---|---|
| `DROPLET_HOST` | DigitalOcean Droplet IP or hostname |
| `DROPLET_USER` | SSH user (e.g., `root` or `deploy`) |
| `DROPLET_SSH_KEY` | Private SSH key for Droplet access |

Note: `GITHUB_TOKEN` is automatically available — no manual setup needed for GHCR push.

### Droplet Setup Prerequisites (Manual, One-Time)

These are NOT automated by this story — they are operator prerequisites:

1. Docker and Docker Compose installed on Droplet
2. Caddy installed on Droplet (via official package repo)
3. Host environment variables set (DATABASE_URL, JWT_SECRET_KEY, REDIS_PASSWORD, etc.)
4. Wallet files placed at `WALLET_PATH` with 700 permissions
5. Firewall: ports 80, 443 open; port 22 for SSH; port 8000 internal only
6. GitHub repo secrets configured (DROPLET_HOST, DROPLET_USER, DROPLET_SSH_KEY)

### Project Structure Notes

New files:
```
.github/
└── workflows/
    ├── ci.yml                        # CI: lint + test + dashboard build
    └── deploy.yml                    # Deploy: build image, push to GHCR, SSH deploy
docker-compose.prod.yml              # Production compose (gateway + redis, no postgres)
```

Modified files:
```
Caddyfile                             # Replace placeholder domain with env var pattern
.env.example                          # Add LOG_FORMAT and production notes
gateway/core/config.py                # Add log_format setting
gateway/core/logging.py               # Conditional JSON/console renderer
```

### Testing Standards

- **No new application tests** — this story is infrastructure configuration
- **CI workflow validation** — the CI workflow itself validates all checks (lint, type check, test, dashboard build)
- **Docker build verification** — `docker build -t tao-gateway:test .` must succeed
- **Compose validation** — `docker compose -f docker-compose.prod.yml config` must succeed
- **After completion**: Run `uv run pytest --tb=short -q`, `uv run ruff check gateway/ tests/`, `uv run mypy gateway/`
- **Existing test count**: ~571 tests should continue passing

### Previous Story Intelligence (Stories 6.1 & 6.2)

- **Story 6.1** completed all admin API endpoints with `is_admin` auth, 571 tests passing
- **Story 6.2** is `ready-for-dev` — adds admin dashboard views (frontend-only). Independent of this story.
- **Branch naming pattern**: `feat/story-6.3-production-deployment-pipeline`
- **Commit message pattern**: `feat: add <description> (Story 6.3)`
- **PR pattern**: feature branches merged via PR with squash merge

### Git Intelligence (Recent Commits)

- `cc4e929` feat: add admin API endpoints with is_admin auth and operator metrics (Story 6.1) (#39)
- `2a746fa` chore: add Story 6.1 spec, code scan plan, and uncommitted dashboard assets (#38)
- Pattern: feature branches merged via PR with squash
- Expected branch: `feat/story-6.3-production-deployment-pipeline`

### Security Considerations

- **GitHub Secrets** — SSH key and Droplet host must be stored as GitHub repo secrets, never in workflow files
- **GHCR authentication** — uses `GITHUB_TOKEN` (automatic), not personal access tokens
- **Production .env** — no `.env` file on Droplet. All secrets as host environment variables (set via `/etc/environment` or systemd service files)
- **Wallet permissions** — mounted as read-only (`:ro`) in Docker, host directory has 700 permissions
- **SSH deploy** — use a dedicated deploy user with limited sudo, not root (recommended but not enforced by this story)
- **Health endpoint** — `/v1/health` is unauthenticated by design (needed for Docker HEALTHCHECK and deployment verification)
- **No secrets in Docker image** — the image contains only code and dependencies, never credentials

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6, Story 6.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment — DO Droplet, Managed Postgres, Caddy, GitHub Actions]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure — .github/workflows/ci.yml, deploy.yml, docker-compose.prod.yml, Caddyfile]
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision: Hosting — DigitalOcean Droplet]
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision: CI/CD — GitHub Actions, test → build → SSH deploy on merge to main]
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision: Reverse proxy — Caddy, auto-TLS, ~5 lines config]
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision: Containerization — Docker Compose, local dev and production]
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision: Secrets management — host env vars, pydantic-settings]
- [Source: _bmad-output/planning-artifacts/prd.md#FR36 — TLS on all endpoints]
- [Source: _bmad-output/planning-artifacts/prd.md#NFR: Security — TLS 1.2+]
- [Source: Dockerfile — Multi-stage build, non-root user, healthcheck]
- [Source: docker-compose.yml — Local dev compose, reference for prod version]
- [Source: Caddyfile — Security headers, TLS config, reverse proxy, placeholder domain]
- [Source: .env.example — Current env var template]
- [Source: gateway/core/config.py — pydantic-settings, env var loading]
- [Source: gateway/core/logging.py — structlog configuration, needs JSON renderer option]
- [Source: gateway/api/health.py — Health endpoint for deployment verification]
- [Source: _bmad-output/implementation-artifacts/6-1-admin-api-endpoints.md — Previous story patterns and learnings]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
