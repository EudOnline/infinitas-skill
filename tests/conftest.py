from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, close_all_sessions

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from tests.helpers.cli import CliResult, run_cli  # noqa: E402
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


@pytest.fixture
def db(tmp_path: Path) -> Session:
    """Create a test database session with migrations.

    This fixture sets up an in-memory SQLite database for testing
    repository operations. The database is migrated and isolated
    for each test.
    """
    # Set up test environment
    db_path = tmp_path / "test.db"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ENV"] = "test"

    from server.db import get_engine, get_session_factory

    # Create engine and run migrations
    engine = get_engine()
    session_factory = get_session_factory()

    # Run migrations
    from alembic.config import Config

    from alembic import command

    alembic_dir = ROOT / "alembic"
    if alembic_dir.exists():
        alembic_cfg = Config(str(ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        command.upgrade(alembic_cfg, "head")

    # Create and yield session
    session = session_factory()
    yield session

    # Cleanup
    session.close()
    close_all_sessions()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def cli_runner():
    """Return a helper that runs ``infinitas <args>`` in a repo.

    Binds the regression env (skip-flags on, require-flags off) plus
    ``PYTHONPATH=<repo>/src``. Replaces the copy-pasted ``run_cli`` in the
    shadow scripts. Usage::

        result = cli_runner(repo, ["install", "resolve-skill", "demo-skill", "--json"])
        assert result.json()["state"] == "resolved-private"
    """

    def _run(
        repo: Path,
        args: list[str],
        *,
        expect: int | None = 0,
        extra_env: dict[str, str] | None = None,
    ) -> CliResult:
        env = make_test_env(extra_env)
        env["PYTHONPATH"] = str(repo / "src")
        return run_cli(repo, args, env=env, expect=expect)

    return _run


@pytest.fixture
def db_at_revision(tmp_path: Path):
    """Factory: migrate a fresh sqlite DB to an arbitrary *revision*.

    Unlike the ``db`` fixture (always ``head``), this supports tests that pin a
    partial migration (e.g. the legacy plaintext-token cutover at ``20260329_0004``).
    Mark such tests ``@pytest.mark.alembic_partial``.
    """

    def _upgrade(revision: str) -> Session:
        db_path = tmp_path / "test.db"
        os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
        os.environ["INFINITAS_SERVER_ENV"] = "test"

        from server.db import get_engine, get_session_factory

        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config(str(ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(ROOT / "alembic"))
        command.upgrade(alembic_cfg, revision)
        return get_session_factory()()

    return _upgrade
