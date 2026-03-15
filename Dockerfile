# --- Build stage ---
FROM python:3.12-slim@sha256:ccc7089399c8bb65dd1fb3ed6d55efa538a3f5e7fca3f5988ac3b5b87e593bf0 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY gateway/ gateway/
COPY alembic.ini ./
COPY migrations/ migrations/

# --- Runtime stage ---
FROM python:3.12-slim@sha256:ccc7089399c8bb65dd1fb3ed6d55efa538a3f5e7fca3f5988ac3b5b87e593bf0

WORKDIR /app

# Copy installed venv and app code from builder
COPY --from=builder /app /app

RUN groupadd --system app && useradd --system --gid app app \
    && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')"]

CMD [".venv/bin/uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
