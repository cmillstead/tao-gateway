"""Shared Redis + in-memory fallback rate limiter.

Provides a fixed-window rate limit backed by Redis (via Lua script) with an
in-memory fallback that activates when Redis is unavailable.  The fallback
uses TTL-based eviction and a size cap to prevent unbounded memory growth.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from gateway.core.redis import get_redis, reset_redis

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Redis Lua script: INCR the counter and set EXPIRE only when the key is
# first created (INCR returns 1).  This gives a true fixed-window rate limit
# instead of resetting the TTL on every request.
# ---------------------------------------------------------------------------
_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""

# ---------------------------------------------------------------------------
# In-memory fallback rate limiter
# ---------------------------------------------------------------------------
_FALLBACK_MAX_ENTRIES = 10_000


class _FallbackStore:
    """Per-key (count, window_start) tracker with TTL eviction and size cap."""

    def __init__(self) -> None:
        # key -> (window_start, count)
        self._entries: dict[str, tuple[float, int]] = {}

    def check(self, key: str, limit: int, window: float) -> bool:
        """Return True if the request should be allowed, False if rate-limited."""
        now = time.monotonic()
        self._evict(now, window)

        entry = self._entries.get(key)
        if entry is None or now - entry[0] >= window:
            self._entries[key] = (now, 1)
            return True
        window_start, count = entry
        if count > limit:
            return False
        self._entries[key] = (window_start, count + 1)
        return True

    def _evict(self, now: float, window: float) -> None:
        """Purge entries whose window has expired, and enforce size cap."""
        # Only run full eviction when we exceed the cap – keeps the hot path
        # cheap for normal traffic.
        if len(self._entries) <= _FALLBACK_MAX_ENTRIES:
            return
        self._entries = {
            k: v for k, v in self._entries.items() if now - v[0] < window
        }
        # If still over cap after TTL eviction, drop oldest entries
        if len(self._entries) > _FALLBACK_MAX_ENTRIES:
            sorted_keys = sorted(self._entries, key=lambda k: self._entries[k][0])
            for k in sorted_keys[: len(self._entries) - _FALLBACK_MAX_ENTRIES]:
                del self._entries[k]

    def clear(self) -> None:
        """Clear all entries (useful for tests)."""
        self._entries.clear()


_fallback_store = _FallbackStore()

# Cache the registered Redis script handle and the Redis instance it belongs to
# so we re-register if the connection is recycled.
_lua_script: Any = None
_lua_script_redis: object | None = None


async def check_rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int = 60,
    fallback_limit: int = 10,
    fallback_window: float = 60.0,
    log_prefix: str = "rate_limit",
) -> int | None:
    """Check a fixed-window rate limit.

    Returns the current request count on success.
    When Redis is unavailable, falls back to the in-memory limiter and returns
    ``None`` if the request is allowed.

    Raises nothing on its own -- callers decide what to do with the count.
    On Redis failure the in-memory fallback is used; if *that* denies the
    request this function returns ``-1``.
    """
    global _lua_script, _lua_script_redis  # noqa: PLW0603
    try:
        redis = await get_redis()
        if _lua_script is None or _lua_script_redis is not redis:
            _lua_script = redis.register_script(_RATE_LIMIT_LUA)
            _lua_script_redis = redis
        raw_result = await _lua_script(keys=[key], args=[window_seconds])
        return int(raw_result)
    except Exception:
        logger.warning("rate_limit_redis_unavailable", source=log_prefix)
        await reset_redis()
        # In-memory fallback
        if not _fallback_store.check(key, fallback_limit, fallback_window):
            return -1
        return None


def clear_fallback_store() -> None:
    """Reset the in-memory fallback store (for tests)."""
    _fallback_store.clear()
