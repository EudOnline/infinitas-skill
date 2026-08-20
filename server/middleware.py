from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from server.logging import get_logger
from server.modules.identity.auth import validate_csrf_token

logger = get_logger(__name__)


class TrustedProxySchemeMiddleware:
    """Apply forwarded HTTPS scheme only when the peer is a trusted proxy."""

    def __init__(self, app: ASGIApp, *, trusted_proxies: list[str]) -> None:
        self.app = app
        self.trusted_proxies = frozenset(trusted_proxies)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self._is_trusted_peer(scope):
            forwarded_proto = self._forwarded_proto(scope)
            if forwarded_proto is not None:
                scope = dict(scope)
                scope["scheme"] = forwarded_proto
        await self.app(scope, receive, send)

    def _is_trusted_peer(self, scope: Scope) -> bool:
        client = scope.get("client")
        return bool(client and client[0] in self.trusted_proxies)

    @staticmethod
    def _forwarded_proto(scope: Scope) -> str | None:
        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"x-forwarded-proto", b"").decode("latin-1")
        proto = raw.split(",", 1)[0].strip().lower()
        return proto if proto in {"http", "https"} else None


class RequestContextMiddleware:
    """Attach a server-generated correlation ID to every HTTP response and log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' "
                    "'sha256-Bn5g5YFE2knf3df736jiCF0Yao9wmuW+tCibG1uamiE='; "
                    "img-src 'self' data:; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "object-src 'none'; "
                    "form-action 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'"
                )
                headers["X-Frame-Options"] = "DENY"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=()"
                )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class CsrfValidationMiddleware:
    """ASGI middleware that validates CSRF tokens for cookie-authenticated requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        try:
            validate_csrf_token(request)
        except Exception as exc:
            status_code = getattr(exc, "status_code", 403)
            detail = getattr(exc, "detail", "Forbidden")
            response = JSONResponse({"detail": detail}, status_code=status_code)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
