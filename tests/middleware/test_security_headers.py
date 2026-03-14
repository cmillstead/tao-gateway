"""Tests for security response headers middleware."""

import pytest
from httpx import AsyncClient

from gateway.core.config import settings


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    """All security headers should be present on responses."""
    resp = await client.get("/v1/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-xss-protection") == "0"
    assert "default-src" in resp.headers.get("content-security-policy", "")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_hsts_absent_in_debug_mode(client: AsyncClient) -> None:
    """HSTS should not be set when debug=True (local dev)."""
    assert settings.debug is True, "This test requires DEBUG=true (set in conftest.py)"
    resp = await client.get("/v1/health")
    assert "strict-transport-security" not in resp.headers


@pytest.mark.asyncio
async def test_security_headers_on_error_responses(client: AsyncClient) -> None:
    """Security headers must be present even on error responses."""
    resp = await client.get("/nonexistent-path")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
