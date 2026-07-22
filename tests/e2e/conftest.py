from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, browser_name):
    """Keep headless Chromium stable on memory-constrained CI runners."""
    if browser_name != "chromium":
        return browser_type_launch_args
    launch_args = list(browser_type_launch_args.get("args") or [])
    options = {
        **browser_type_launch_args,
        "args": [*launch_args, "--disable-gpu", "--renderer-process-limit=1"],
    }
    options.setdefault("channel", "chromium-headless-shell")
    return options


@pytest.fixture(scope="session")
def tmpdir_session():
    d = Path(tempfile.mkdtemp(prefix="infinitas-e2e-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _find_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_server(url: str, thread: threading.Thread, *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError("E2E server stopped before becoming ready")
        try:
            with urllib.request.urlopen(f"{url}/api/v1/system/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError(f"E2E server did not become ready within {timeout:g}s") from last_error


@pytest.fixture(scope="session")
def live_server(tmpdir_session):
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir_session / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir_session / "artifacts")
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "e2e-maintainer",
                "display_name": "E2E Maintainer",
                "role": "maintainer",
                "token": "e2e-maintainer-token",
                "password": "e2e-maintainer-password",
            },
        ]
    )

    import uvicorn

    from server.app import create_app

    app = create_app()
    port = _find_free_port()
    address = f"http://127.0.0.1:{port}"
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    server = threading.Thread(
        target=uvicorn_server.run,
        daemon=True,
    )
    server.start()
    _wait_for_server(address, server)
    yield address
    uvicorn_server.should_exit = True
    server.join(timeout=10)
    if server.is_alive():
        pytest.fail("E2E server did not stop within 10s")


@pytest.fixture
def page(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(live_server, wait_until="domcontentloaded")
    yield pg
    context.close()


@pytest.fixture
def authenticated_page(live_server, browser):
    from server.db import get_session_factory
    from server.rate_limit import get_rate_limiter

    get_rate_limiter().reset_all()
    session_factory = get_session_factory()
    with session_factory() as db:
        get_rate_limiter(db).reset_all()
        db.commit()
    context = browser.new_context()
    response = context.request.post(
        f"{live_server}/api/v1/auth/login?lang=en",
        data={"username": "e2e-maintainer", "password": "e2e-maintainer-password"},
    )
    assert response.status == 200
    assert response.json()["success"] is True
    pg = context.new_page()
    pg.goto(f"{live_server}/?lang=en", wait_until="domcontentloaded")
    pg.wait_for_selector("#global-search")
    yield pg
    context.close()
