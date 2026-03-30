from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

pytest_plugins = ["tests.fixtures.repo_state"]


@pytest.fixture(autouse=True)
def clear_server_caches():
    from server.db import get_engine, get_session_factory
    from server.settings import get_settings

    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
    yield
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
