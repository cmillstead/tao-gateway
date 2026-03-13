# tao-gateway

## Testing

- Always use the real thing over mocks when possible. Hit real Postgres and Redis (via Docker test containers) instead of mocking.
- Only mock external services that are impractical to run locally (e.g., Bittensor SDK).
- Run tests: `uv run pytest --tb=short -q`
- Run linter: `uv run ruff check gateway/ tests/`
- Run type checker: `uv run mypy gateway/`

## Tech Stack

- Python 3.12, FastAPI, SQLAlchemy 2.x (async), Redis (async), Pydantic v2
- Package manager: uv
- Logging: structlog
- Auth: argon2 for API key hashing, JWT for dashboard
