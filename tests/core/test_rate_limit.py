"""Tests for gateway.core.rate_limit — fallback store and check_rate_limit."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from gateway.core.rate_limit import SimpleRateLimitResult, _FallbackStore, check_rate_limit


class TestFallbackStore:
    """Unit tests for the in-memory fallback rate limiter."""

    def test_allows_within_limit(self):
        store = _FallbackStore()
        assert store.check("k", limit=3, window=60) is True
        assert store.check("k", limit=3, window=60) is True
        assert store.check("k", limit=3, window=60) is True

    def test_denies_over_limit(self):
        store = _FallbackStore()
        for _ in range(3):
            store.check("k", limit=3, window=60)
        assert store.check("k", limit=3, window=60) is False

    def test_allows_exactly_limit_not_limit_plus_one(self):
        """Regression: off-by-one bug allowed limit+1 requests (CODE-002)."""
        store = _FallbackStore()
        results = [store.check("k", limit=5, window=60) for _ in range(7)]
        assert results == [True, True, True, True, True, False, False]

    def test_separate_keys_independent(self):
        store = _FallbackStore()
        for _ in range(3):
            store.check("a", limit=3, window=60)
        assert store.check("a", limit=3, window=60) is False
        assert store.check("b", limit=3, window=60) is True

    def test_window_resets_after_expiry(self):
        store = _FallbackStore()
        for _ in range(3):
            store.check("k", limit=3, window=0.01)
        assert store.check("k", limit=3, window=0.01) is False
        time.sleep(0.02)
        assert store.check("k", limit=3, window=0.01) is True

    def test_clear(self):
        store = _FallbackStore()
        for _ in range(3):
            store.check("k", limit=3, window=60)
        store.clear()
        assert store.check("k", limit=3, window=60) is True


class TestCheckRateLimit:
    """Integration tests for check_rate_limit with real Redis."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        result = await check_rate_limit(
            key="test_core_rl:allow",
            limit=5,
            window_seconds=60,
        )
        assert result.allowed is True
        assert result.source == "redis"
        assert result.count == 1

    @pytest.mark.asyncio
    async def test_denies_over_limit(self):
        for _ in range(5):
            await check_rate_limit(key="test_core_rl:deny", limit=5, window_seconds=60)
        result = await check_rate_limit(key="test_core_rl:deny", limit=5, window_seconds=60)
        assert result.allowed is False
        assert result.count == 6

    @pytest.mark.asyncio
    async def test_fallback_when_redis_unavailable(self):
        with patch(
            "gateway.core.rate_limit.get_redis",
            new_callable=AsyncMock,
            side_effect=ConnectionError("down"),
        ):
            result = await check_rate_limit(
                key="test_core_rl:fallback",
                limit=5,
                window_seconds=60,
                fallback_limit=3,
            )
            assert isinstance(result, SimpleRateLimitResult)
            assert result.source == "fallback"
            assert result.allowed is True
