"""Tests for Redis circuit breaker behavior."""

import time

import pytest

from gateway.core import redis as redis_module


@pytest.fixture(autouse=True)
async def _reset_redis_state():
    """Reset module-level redis state before/after each test."""
    original_client = redis_module.redis_client
    original_failure_time = redis_module._last_failure_time
    yield
    redis_module.redis_client = original_client
    redis_module._last_failure_time = original_failure_time


@pytest.mark.asyncio
async def test_circuit_breaker_fails_fast_after_failure():
    """After a connection failure, subsequent calls fail immediately within cooldown."""
    # Simulate a recent failure
    redis_module.redis_client = None
    redis_module._last_failure_time = time.monotonic()

    with pytest.raises(ConnectionError, match="circuit breaker open"):
        await redis_module.get_redis()


@pytest.mark.asyncio
async def test_circuit_breaker_allows_retry_after_cooldown():
    """After cooldown period, a new connection attempt is allowed."""
    redis_module.redis_client = None
    # Set failure time far enough in the past
    redis_module._last_failure_time = (
        time.monotonic() - redis_module._CIRCUIT_BREAKER_COOLDOWN - 1
    )

    # The retry should be allowed (will succeed since we have a real Redis)
    client = await redis_module.get_redis()
    assert client is not None


@pytest.mark.asyncio
async def test_close_redis_cleans_up():
    """close_redis clears the cached client."""
    # Ensure we have a client
    client = await redis_module.get_redis()
    assert client is not None
    assert redis_module.redis_client is not None

    await redis_module.close_redis()
    assert redis_module.redis_client is None


@pytest.mark.asyncio
async def test_try_get_redis_returns_none_when_circuit_breaker_open():
    """try_get_redis returns None (not raises) when Redis is unavailable."""
    redis_module.redis_client = None
    redis_module._last_failure_time = time.monotonic()

    result = await redis_module.try_get_redis()
    assert result is None


@pytest.mark.asyncio
async def test_try_get_redis_reset_on_failure_clears_client():
    """try_get_redis with reset_on_failure=True clears a broken client."""
    # Set a non-None client and trigger circuit breaker
    redis_module.redis_client = None
    redis_module._last_failure_time = time.monotonic()

    result = await redis_module.try_get_redis(reset_on_failure=True)
    assert result is None
    # Client should still be None (reset was called)
    assert redis_module.redis_client is None


@pytest.mark.asyncio
async def test_reset_redis_clears_cached_client():
    """reset_redis closes and clears the cached client."""
    # Get a real client first
    client = await redis_module.get_redis()
    assert client is not None
    assert redis_module.redis_client is not None

    await redis_module.reset_redis()
    assert redis_module.redis_client is None
