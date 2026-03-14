#!/usr/bin/env bash
# Generate TypeScript API client from FastAPI's OpenAPI spec.
# Usage: ./scripts/generate_api_client.sh
#
# Generates dashboard/src/api/schema.d.ts from the backend's OpenAPI spec.
# Tries a running server first; falls back to extracting the spec via Python import.
# The generated schema.d.ts should be committed to git.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
OUTPUT_FILE="$DASHBOARD_DIR/src/api/schema.d.ts"
SPEC_URL="http://localhost:8000/openapi.json"

mkdir -p "$DASHBOARD_DIR/src/api"

SPEC_FILE=""
cleanup() {
  if [ -n "$SPEC_FILE" ] && [ -f "$SPEC_FILE" ]; then
    rm -f "$SPEC_FILE"
  fi
}
trap cleanup EXIT

# Try to fetch from a running server
if curl -sf "$SPEC_URL" -o /dev/null 2>/dev/null; then
  echo "Using running server at $SPEC_URL"
  SPEC_SOURCE="$SPEC_URL"
else
  echo "No running server detected. Extracting OpenAPI spec via Python import..."
  SPEC_FILE="$(mktemp "${TMPDIR:-/tmp}/openapi-spec.XXXXXX.json")"
  cd "$PROJECT_ROOT"

  # Set minimal env vars if not already set (only needed for spec extraction, not DB connections)
  export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://user:pass@localhost:5432/db}"
  export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
  export JWT_SECRET_KEY="${JWT_SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"

  uv run python -c "
import json
from gateway.main import app
spec = app.openapi()
with open('$SPEC_FILE', 'w') as f:
    json.dump(spec, f, indent=2)
"

  echo "OpenAPI spec extracted to temp file"
  SPEC_SOURCE="$SPEC_FILE"
fi

# Generate TypeScript types
cd "$DASHBOARD_DIR"
npx openapi-typescript "$SPEC_SOURCE" -o "$OUTPUT_FILE"

echo ""
echo "Generated: $OUTPUT_FILE"
