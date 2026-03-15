"""Security response headers middleware.

Adds standard security headers to all responses as defense-in-depth.
Caddy also sets these at the reverse proxy layer; the application middleware
ensures they are present even when running without Caddy (dev, tests).

Uses a pure ASGI middleware pattern instead of BaseHTTPMiddleware to avoid
potential issues with streaming responses (SSE).
"""

from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from gateway.core.config import settings

_COMMON_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"x-xss-protection", b"0"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
]

_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
_SPA_CSP = (
    b"content-security-policy",
    b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    b" img-src 'self' data:; font-src 'self'",
)

_HSTS_HEADER: tuple[bytes, bytes] = (
    b"strict-transport-security",
    b"max-age=31536000; includeSubDomains",
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_api = path.startswith(("/v1/", "/auth/", "/admin/", "/dashboard/"))

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_COMMON_HEADERS)
                headers.append(_API_CSP if is_api else _SPA_CSP)
                if not settings.debug:
                    headers.append(_HSTS_HEADER)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
