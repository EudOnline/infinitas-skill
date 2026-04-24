from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def tmpdir_session():
    d = Path(tempfile.mkdtemp(prefix="infinitas-e2e-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def live_server(tmpdir_session):
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
            },
        ]
    )

    import uvicorn
    import threading
    import time

    from server.app import create_app

    app = create_app()
    port = 18923
    server = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": port, "log_level": "error"},
        daemon=True,
    )
    server.start()
    time.sleep(1.0)
    yield f"http://127.0.0.1:{port}"


@pytest.fixture
def page(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(live_server)
    yield pg
    context.close()


@pytest.fixture
def authenticated_page(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(f"{live_server}/login?lang=en")
    pg.wait_for_selector("#login-token-input")
    pg.fill("#login-token-input", "e2e-maintainer-token")
    pg.click("#login-login-btn")
    pg.wait_for_load_state("networkidle")
    yield pg
    context.close()
