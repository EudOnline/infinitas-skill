from __future__ import annotations

import asyncio

from server.middleware import TrustedProxySchemeMiddleware


def _run_middleware(scope: dict) -> dict:
    captured: dict = {}

    async def app(inner_scope, _receive, _send):
        captured.update(inner_scope)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    asyncio.run(
        TrustedProxySchemeMiddleware(app, trusted_proxies=["10.0.0.2"])(scope, receive, send)
    )
    return captured


def test_forwarded_https_is_applied_for_trusted_peer() -> None:
    scope = {
        "type": "http",
        "scheme": "http",
        "client": ("10.0.0.2", 1234),
        "headers": [(b"x-forwarded-proto", b"https, http")],
    }

    assert _run_middleware(scope)["scheme"] == "https"


def test_forwarded_https_is_ignored_for_untrusted_peer() -> None:
    scope = {
        "type": "http",
        "scheme": "http",
        "client": ("198.51.100.8", 1234),
        "headers": [(b"x-forwarded-proto", b"https")],
    }

    assert _run_middleware(scope)["scheme"] == "http"
