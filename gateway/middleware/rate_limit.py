"""Multi-window per-key×per-subnet rate limiter.

Enforces three time windows (minute/day/month) per API key per subnet
using an atomic Redis Lua script. Fails closed when Redis is unavailable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from gateway.core.exceptions import RateLimitExceededError
from gateway.core.redis import get_redis, reset_redis

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger()

_LUA_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "rate_limit.lua"
_LUA_SOURCE: str = _LUA_SCRIPT_PATH.read_text()

# Cached script handle and the Redis instance it was registered on.
_lua_script: Any = None
_lua_script_redis: object | None = None

# Window durations in seconds
MINUTE_WINDOW = 60
DAY_WINDOW = 86400
MONTH_WINDOW = 2592000  # 30 days

# Default rate limits (free tier) per subnet netuid
_DEFAULT_LIMITS: dict[str, int] = {"minute": 10, "day": 100, "month": 1000}

_SUBNET_RATE_LIMITS: dict[int, dict[str, int]] = {
    1: {"minute": 10, "day": 100, "month": 1000},   # SN1
    19: {"minute": 5, "day": 50, "month": 500},      # SN19
    62: {"minute": 10, "day": 100, "month": 1000},   # SN62
    32: {"minute": 60, "day": 600, "month": 6000},    # SN32 detection
    22: {"minute": 30, "day": 300, "month": 3000},     # SN22 search
}


def get_subnet_rate_limits(netuid: int) -> dict[str, int]:
    """Return rate limits for a given subnet netuid (always a fresh copy)."""
    return dict(_SUBNET_RATE_LIMITS.get(netuid, _DEFAULT_LIMITS))


@dataclass(slots=True)
class RateLimitResult:
    """Result from a rate limit check."""

    allowed: bool
    minute_count: int
    minute_remaining: int
    minute_reset: int  # unix timestamp
    day_count: int
    day_remaining: int
    day_reset: int
    month_count: int
    month_remaining: int
    month_reset: int
    # Most restrictive window info
    limit: int
    remaining: int
    reset: int  # unix timestamp of most restrictive window
    retry_after: int  # seconds until most restrictive exceeded window resets (0 if allowed)

    def to_headers(self) -> dict[str, str]:
        """Return rate limit response headers."""
        headers: dict[str, str] = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


async def load_lua_script(redis: Redis) -> Any:
    """Load and register the Lua rate limit script with Redis."""
    global _lua_script, _lua_script_redis  # noqa: PLW0603
    if _lua_script is not None and _lua_script_redis is redis:
        return _lua_script
    _lua_script = redis.register_script(_LUA_SOURCE)
    _lua_script_redis = redis
    return _lua_script


def _compute_most_restrictive(
    limits: dict[str, int],
    minute_remaining: int,
    minute_reset: int,
    day_remaining: int,
    day_reset: int,
    month_remaining: int,
    month_reset: int,
    allowed: bool,
) -> tuple[int, int, int, int]:
    """Find the most restrictive window and return (limit, remaining, reset, retry_after).

    Most restrictive = the window with the lowest remaining count
    relative to its limit (i.e., the one closest to being exceeded).
    """
    windows = [
        (limits["minute"], minute_remaining, minute_reset),
        (limits["day"], day_remaining, day_reset),
        (limits["month"], month_remaining, month_reset),
    ]

    # Find which windows are exhausted (remaining <= 0)
    exhausted = [(lim, rem, rst) for lim, rem, rst in windows if rem <= 0]

    if exhausted and not allowed:
        # Return the exhausted window with the longest retry_after
        now = int(time.time())
        lim, rem, rst = max(exhausted, key=lambda w: w[2])
        return lim, 0, rst, max(0, rst - now)

    # No windows exhausted — return the one with lowest remaining
    lim, rem, rst = min(windows, key=lambda w: w[1])
    return lim, rem, rst, 0


async def check_rate_limit(
    *,
    key_id: str,
    subnet_id: str,
    limits: dict[str, int],
) -> RateLimitResult:
    """Check rate limits across three time windows.

    Fails closed (rejects request) when Redis is unavailable.
    """
    now = int(time.time())

    try:
        redis = await get_redis()
        script = await load_lua_script(redis)

        keys = [
            f"rate:{key_id}:{subnet_id}:m",
            f"rate:{key_id}:{subnet_id}:d",
            f"rate:{key_id}:{subnet_id}:M",
        ]

        raw = await script(
            keys=keys,
            args=[
                limits["minute"],
                limits["day"],
                limits["month"],
                MINUTE_WINDOW,
                DAY_WINDOW,
                MONTH_WINDOW,
            ],
        )

        allowed = int(raw[0]) == 1
        minute_count = int(raw[1])
        minute_ttl = max(int(raw[2]), 0)
        day_count = int(raw[3])
        day_ttl = max(int(raw[4]), 0)
        month_count = int(raw[5])
        month_ttl = max(int(raw[6]), 0)

        minute_remaining = limits["minute"] - minute_count
        day_remaining = limits["day"] - day_count
        month_remaining = limits["month"] - month_count

        minute_reset = now + minute_ttl
        day_reset = now + day_ttl
        month_reset = now + month_ttl

        limit, remaining, reset, retry_after = _compute_most_restrictive(
            limits,
            minute_remaining, minute_reset,
            day_remaining, day_reset,
            month_remaining, month_reset,
            allowed=allowed,
        )

        return RateLimitResult(
            allowed=allowed,
            minute_count=minute_count,
            minute_remaining=minute_remaining,
            minute_reset=minute_reset,
            day_count=day_count,
            day_remaining=day_remaining,
            day_reset=day_reset,
            month_count=month_count,
            month_remaining=month_remaining,
            month_reset=month_reset,
            limit=limit,
            remaining=remaining,
            reset=reset,
            retry_after=retry_after,
        )

    except Exception as exc:
        logger.warning("rate_limit_redis_unavailable", key_id=key_id, subnet_id=subnet_id)
        await reset_redis()
        # Fail closed: reject the request when Redis is unavailable
        raise RateLimitExceededError(
            message="Rate limiting temporarily unavailable. Please retry.",
            retry_after=5,
        ) from exc


async def enforce_rate_limit(key_id: str, netuid: int, subnet_name: str) -> RateLimitResult:
    """Check rate limits and raise RateLimitExceededError if denied.

    Shared by all subnet endpoints. Returns the result for header injection.
    """
    limits = get_subnet_rate_limits(netuid)
    result = await check_rate_limit(key_id=key_id, subnet_id=subnet_name, limits=limits)
    if not result.allowed:
        raise RateLimitExceededError(
            message=(
                f"Rate limit exceeded for {subnet_name.upper()}. "
                f"Retry after {result.retry_after} seconds."
            ),
            subnet=subnet_name,
            retry_after=result.retry_after,
        )
    return result
