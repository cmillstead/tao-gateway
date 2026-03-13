# --- Build stage ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY gateway/ gateway/
COPY alembic.ini ./
COPY migrations/ migrations/

# --- Runtime stage ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed venv and app code from builder
COPY --from=builder /app /app

RUN groupadd --system app && useradd --system --gid app app \
    && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/v1/health"]

CMD [".venv/bin/uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
