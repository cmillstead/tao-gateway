"""Tests for the multi-window per-key×per-subnet rate limiter.

Uses real Redis — no mocking.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from gateway.core.redis import get_redis
from gateway.middleware.rate_limit import (
    check_rate_limit,
    get_subnet_rate_limits,
    load_lua_script,
)

# Tiny limits to keep tests fast
_TEST_LIMITS = {"minute": 3, "day": 10, "month": 50}


# ---- Task 1: Lua script tests ----


class TestLuaScript:
    """Verify the Lua script handles multi-window rate limiting atomically."""

    async def test_load_lua_script(self):
        """Script loads and returns a callable."""
        redis = await get_redis()
        script = await load_lua_script(redis)
        assert script is not None

    async def test_first_request_allowed(self):
        """First request within all windows is allowed."""
        result = await check_rate_limit(
            key_id="test-key-1",
            subnet_id="sn1",
            limits=_TEST_LIMITS,
        )
        assert result.allowed is True
        assert result.minute_remaining == _TEST_LIMITS["minute"] - 1
        assert result.day_remaining == _TEST_LIMITS["day"] - 1
        assert result.month_remaining == _TEST_LIMITS["month"] - 1

    async def test_minute_limit_exceeded(self):
        """After minute limit is hit, subsequent requests are denied."""
        for _ in range(_TEST_LIMITS["minute"]):
            result = await check_rate_limit(
                key_id="test-key-2", subnet_id="sn1", limits=_TEST_LIMITS
            )
            assert result.allowed is True

        result = await check_rate_limit(
            key_id="test-key-2", subnet_id="sn1", limits=_TEST_LIMITS
        )
        assert result.allowed is False
        assert result.retry_after > 0

    async def test_per_subnet_independence(self):
        """Hitting limit on SN1 does not affect SN19."""
        for _ in range(_TEST_LIMITS["minute"]):
            await check_rate_limit(
                key_id="test-key-3", subnet_id="sn1", limits=_TEST_LIMITS
            )

        # SN1 should be blocked
        sn1_result = await check_rate_limit(
            key_id="test-key-3", subnet_id="sn1", limits=_TEST_LIMITS
        )
        assert sn1_result.allowed is False

        # SN19 should still work
        sn19_result = await check_rate_limit(
            key_id="test-key-3", subnet_id="sn19", limits=_TEST_LIMITS
        )
        assert sn19_result.allowed is True

    async def test_per_key_independence(self):
        """Hitting limit on key-A does not affect key-B."""
        for _ in range(_TEST_LIMITS["minute"]):
            await check_rate_limit(
                key_id="key-A", subnet_id="sn1", limits=_TEST_LIMITS
            )

        # key-A blocked
        result_a = await check_rate_limit(
            key_id="key-A", subnet_id="sn1", limits=_TEST_LIMITS
        )
        assert result_a.allowed is False

        # key-B still works
        result_b = await check_rate_limit(
            key_id="key-B", subnet_id="sn1", limits=_TEST_LIMITS
        )
        assert result_b.allowed is True

    async def test_atomic_concurrent_requests(self):
        """Concurrent requests don't create race conditions."""
        limit = 5
        limits = {"minute": limit, "day": 100, "month": 1000}
        results = await asyncio.gather(
            *[
                check_rate_limit(key_id="conc-key", subnet_id="sn1", limits=limits)
                for _ in range(limit + 3)
            ]
        )
        allowed = sum(1 for r in results if r.allowed)
        denied = sum(1 for r in results if not r.allowed)
        assert allowed == limit
        assert denied == 3

    async def test_day_limit_exceeded(self):
        """Daily limit enforcement works."""
        day_limits = {"minute": 100, "day": 3, "month": 50}
        for _ in range(3):
            result = await check_rate_limit(
                key_id="day-key", subnet_id="sn19", limits=day_limits
            )
            assert result.allowed is True

        result = await check_rate_limit(
            key_id="day-key", subnet_id="sn19", limits=day_limits
        )
        assert result.allowed is False
        # Retry-after should reflect the daily window reset (large number)
        assert result.retry_after > 60

    async def test_month_limit_exceeded(self):
        """Monthly limit enforcement works."""
        month_limits = {"minute": 100, "day": 100, "month": 3}
        for _ in range(3):
            result = await check_rate_limit(
                key_id="month-key", subnet_id="sn62", limits=month_limits
            )
            assert result.allowed is True

        result = await check_rate_limit(
            key_id="month-key", subnet_id="sn62", limits=month_limits
        )
        assert result.allowed is False
        assert result.retry_after > 86400

    async def test_result_contains_reset_times(self):
        """Result includes reset timestamps for all windows."""
        result = await check_rate_limit(
            key_id="reset-key", subnet_id="sn1", limits=_TEST_LIMITS
        )
        now = int(time.time())
        assert result.minute_reset > now
        assert result.day_reset > now
        assert result.month_reset > now
        # Minute reset should be within ~60s
        assert result.minute_reset <= now + 61

    async def test_most_restrictive_window(self):
        """Rate limit headers reflect the most restrictive active window."""
        # Use limits where minute is most restrictive
        limits = {"minute": 2, "day": 100, "month": 1000}
        result = await check_rate_limit(
            key_id="restrict-key", subnet_id="sn1", limits=limits
        )
        assert result.limit == 2  # minute is most restrictive
        assert result.remaining == 1


# ---- Task 2: Middleware / response header tests ----


class TestRateLimitHeaders:
    """Verify rate limit response headers are correctly set."""

    async def test_headers_on_success(self):
        """Successful requests include rate limit headers."""
        result = await check_rate_limit(
            key_id="hdr-key", subnet_id="sn1", limits=_TEST_LIMITS
        )
        headers = result.to_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert int(headers["X-RateLimit-Limit"]) == _TEST_LIMITS["minute"]
        assert int(headers["X-RateLimit-Remaining"]) == _TEST_LIMITS["minute"] - 1

    async def test_headers_on_denied(self):
        """Denied requests include Retry-After header."""
        for _ in range(_TEST_LIMITS["minute"]):
            await check_rate_limit(
                key_id="hdr-denied", subnet_id="sn1", limits=_TEST_LIMITS
            )

        result = await check_rate_limit(
            key_id="hdr-denied", subnet_id="sn1", limits=_TEST_LIMITS
        )
        headers = result.to_headers()
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) > 0


# ---- Task 2.7: 429 error body tests ----


class TestRateLimitError:
    """Verify 429 error responses have correct body format."""

    async def test_error_body_format(self):
        """429 errors include type, subnet, retry_after."""
        from gateway.core.exceptions import RateLimitExceededError

        for _ in range(_TEST_LIMITS["minute"]):
            await check_rate_limit(
                key_id="err-key", subnet_id="sn1", limits=_TEST_LIMITS
            )

        result = await check_rate_limit(
            key_id="err-key", subnet_id="sn1", limits=_TEST_LIMITS
        )
        assert result.allowed is False

        # Build error from result (as middleware would)
        exc = RateLimitExceededError(
            message=f"Rate limit exceeded for SN1. Retry after {result.retry_after} seconds.",
            subnet="sn1",
            retry_after=result.retry_after,
        )
        assert exc.status_code == 429
        assert exc.error_type == "rate_limit_exceeded"
        assert exc.subnet == "sn1"
        assert exc.retry_after > 0


# ---- Task 3: Config tests ----


class TestRateLimitConfig:
    """Verify rate limit configuration resolves correctly."""

    def test_get_subnet_rate_limits_sn1(self):
        """SN1 has correct free tier limits."""
        limits = get_subnet_rate_limits(1)
        assert limits["minute"] == 10
        assert limits["day"] == 100
        assert limits["month"] == 1000

    def test_get_subnet_rate_limits_sn19(self):
        """SN19 has lower free tier limits."""
        limits = get_subnet_rate_limits(19)
        assert limits["minute"] == 5
        assert limits["day"] == 50
        assert limits["month"] == 500

    def test_get_subnet_rate_limits_sn62(self):
        """SN62 has same limits as SN1."""
        limits = get_subnet_rate_limits(62)
        assert limits["minute"] == 10
        assert limits["day"] == 100
        assert limits["month"] == 1000

    def test_get_subnet_rate_limits_unknown(self):
        """Unknown subnets get default limits."""
        limits = get_subnet_rate_limits(999)
        assert "minute" in limits
        assert "day" in limits
        assert "month" in limits


# ---- enforce_rate_limit tests ----


class TestEnforceRateLimit:
    """Verify the shared enforce_rate_limit function."""

    async def test_returns_result_when_allowed(self):
        """Returns RateLimitResult when within limits."""
        from gateway.middleware.rate_limit import enforce_rate_limit

        result = await enforce_rate_limit("enf-key-1", 1, "sn1")
        assert result.allowed is True
        assert result.minute_remaining == 9  # SN1 free tier: 10/min

    async def test_raises_rate_limit_exceeded_error(self):
        """Raises RateLimitExceededError with subnet and retry_after when denied."""
        from gateway.core.exceptions import RateLimitExceededError
        from gateway.middleware.rate_limit import enforce_rate_limit

        # Exhaust SN19 limit (5/min)
        for _ in range(5):
            await enforce_rate_limit("enf-key-2", 19, "sn19")

        with pytest.raises(RateLimitExceededError) as exc_info:
            await enforce_rate_limit("enf-key-2", 19, "sn19")

        exc = exc_info.value
        assert exc.status_code == 429
        assert exc.error_type == "rate_limit_exceeded"
        assert exc.subnet == "sn19"
        assert exc.retry_after > 0
        assert "SN19" in exc.message


# ---- Task 5.9: Redis unavailability ----


class TestRateLimitRedisUnavailable:
    """Verify fail-closed behavior when Redis is down (SEC-001)."""

    async def test_fail_closed_when_redis_down(self):
        """Requests are rejected when Redis is unavailable (fail-closed)."""
        from gateway.core.exceptions import RateLimitExceededError

        with (
            patch(
                "gateway.middleware.rate_limit.get_redis",
                new_callable=AsyncMock,
                side_effect=ConnectionError("Redis down"),
            ),
            pytest.raises(RateLimitExceededError),
        ):
            await check_rate_limit(
                key_id="fail-key", subnet_id="sn1", limits=_TEST_LIMITS
            )


# ---- Task 5.10: Integration test ----


class TestRateLimitIntegration:
    """End-to-end: auth → rate limit → handler → response with headers."""

    @pytest.fixture
    async def api_key_token(self):
        """Create an org + API key, return the raw token."""
        from gateway.core.database import get_db
        from gateway.core.security import ph
        from gateway.models.organization import Organization
        from gateway.services.api_key_service import create_api_key

        async for db in get_db():
            org = Organization(
                email=f"ratelimit-test-{time.time_ns()}@example.com",
                password_hash=ph.hash("test"),
            )
            db.add(org)
            await db.commit()
            await db.refresh(org)

            _record, full_key = await create_api_key(org.id, "live", db)
            return full_key

    async def test_rate_limit_headers_on_error_response(self, client, api_key_token):
        """Rate limit headers appear even when the handler raises a non-429 error."""
        from unittest.mock import AsyncMock

        from tests.conftest import app

        # Force adapter.execute to raise a GatewayError (e.g., MinerTimeout)
        mock_dendrite = AsyncMock()
        mock_dendrite.forward.side_effect = Exception("miner down")
        original_dendrite = app.state.dendrite
        app.state.dendrite = mock_dendrite

        try:
            headers = {"Authorization": f"Bearer {api_key_token}"}
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "tao-sn1",
                    "messages": [{"role": "user", "content": "hello"}],
                },
                headers=headers,
            )
            # Should get a 500/502/504 from the miner failure, NOT 429
            assert response.status_code >= 500
            # Rate limit headers should still be present via request.state
            assert "x-ratelimit-limit" in response.headers
            assert "x-ratelimit-remaining" in response.headers
            assert "x-ratelimit-reset" in response.headers
        finally:
            app.state.dendrite = original_dendrite

    async def test_rate_limit_headers_on_endpoint(self, client, api_key_token):
        """Chat endpoint returns rate limit headers on response."""
        headers = {"Authorization": f"Bearer {api_key_token}"}
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "tao-sn1",
                "messages": [{"role": "user", "content": "hello"}],
            },
            headers=headers,
        )
        # Request may fail at adapter level (mocked bittensor), but not 429
        assert response.status_code != 429
        # Rate limit headers must be present regardless of response status
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers
        assert int(response.headers["x-ratelimit-limit"]) == 10  # SN1 free tier
        assert int(response.headers["x-ratelimit-remaining"]) == 9
