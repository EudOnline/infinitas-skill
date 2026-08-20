"""Synchronous ASGI client without AnyIO's cross-thread portal."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

_OPEN_CLIENTS: list["LifespanTestClient"] = []


class _SyncASGITransport(httpx.BaseTransport):
    def __init__(self, app: Any, *, raise_app_exceptions: bool) -> None:
        self.app = app
        self.raise_app_exceptions = raise_app_exceptions

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = request.read()

        async def dispatch() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=self.app,
                raise_app_exceptions=self.raise_app_exceptions,
                client=("testclient", 50000),
            )
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    content=body,
                )
                content = await response.aread()
                return httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=content,
                    request=request,
                    extensions=response.extensions,
                )

        return asyncio.run(dispatch())

    def close(self) -> None:
        return None


class LifespanTestClient(httpx.Client):
    """Test client that runs app readiness without AnyIO portal threads."""

    __test__ = False

    def __init__(self, app: Any, **kwargs: Any) -> None:
        from server.lifecycle import ensure_database_ready

        self.app = app
        ensure_database_ready(app.state.settings)
        transport = _SyncASGITransport(
            app,
            raise_app_exceptions=kwargs.pop("raise_server_exceptions", True),
        )
        kwargs.setdefault("base_url", "http://testserver")
        kwargs.setdefault("follow_redirects", True)
        super().__init__(transport=transport, **kwargs)
        _OPEN_CLIENTS.append(self)

    def __enter__(self) -> "LifespanTestClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def close_test_clients() -> None:
    while _OPEN_CLIENTS:
        client = _OPEN_CLIENTS.pop()
        client.close()


__all__ = ["LifespanTestClient", "close_test_clients"]
