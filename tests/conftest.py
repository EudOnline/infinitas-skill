from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from tests.helpers.env import make_test_env  # noqa: E402
from tests.helpers.repo_copy import copy_repo_without_local_state  # noqa: E402
from tests.helpers.signing import add_allowed_signer, generate_signing_key  # noqa: E402

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


@pytest.fixture
def temp_repo_copy(tmp_path: Path) -> Path:
    return copy_repo_without_local_state(tmp_path)


@pytest.fixture
def test_env() -> dict[str, str]:
    return make_test_env()


@pytest.fixture
def signing_key(tmp_path: Path) -> Path:
    return generate_signing_key(tmp_path, identity="release-test")


@pytest.fixture
def allowed_signers_file(tmp_path: Path, signing_key: Path) -> Path:
    allowed_signers = tmp_path / "allowed_signers"
    add_allowed_signer(allowed_signers, identity="release-test", key_path=signing_key)
    return allowed_signers
