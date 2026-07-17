"""TestClient variant that always runs FastAPI lifespan hooks."""

from __future__ import annotations

from fastapi.testclient import TestClient as _FastAPITestClient

_OPEN_CLIENTS: list["LifespanTestClient"] = []


class LifespanTestClient(_FastAPITestClient):
    """Start the application lifespan for tests that construct clients directly."""

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._lifespan_started = False
        self.__enter__()
        self._lifespan_started = True
        _OPEN_CLIENTS.append(self)

    def close(self) -> None:
        if self._lifespan_started:
            self._lifespan_started = False
            self.__exit__(None, None, None)
        super().close()


def close_test_clients() -> None:
    while _OPEN_CLIENTS:
        client = _OPEN_CLIENTS.pop()
        client.close()


__all__ = ["LifespanTestClient", "close_test_clients"]
