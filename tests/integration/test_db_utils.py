from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from server.db import _engine_kwargs


class TestEngineKwargs:
    def test_sqlite_returns_check_same_thread_false(self):
        kwargs = _engine_kwargs("sqlite:///test.db")
        assert kwargs == {"connect_args": {"check_same_thread": False}}

    def test_non_sqlite_returns_empty(self):
        kwargs = _engine_kwargs("postgresql://user:pass@localhost/db")
        assert kwargs == {}


class TestGetDb:
    def test_get_db_yields_session(self, monkeypatch, tmp_path: Path):
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from server.db import get_db
        gen = get_db()
        session = next(gen)  # noqa: F841
        # Should be able to execute a query
        result = session.execute(text("SELECT 1"))
        assert result.scalar() == 1
        # Clean up
        try:
            next(gen)
        except StopIteration:
            pass

    def test_get_db_rollback_on_exception(self, monkeypatch, tmp_path: Path):
        db_path = tmp_path / "test2.db"
        monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from server.db import get_db
        gen = get_db()
        session = next(gen)  # noqa: F841
        # Simulate an exception
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("test error"))


class TestSessionScope:
    def test_session_scope_commits(self, monkeypatch, tmp_path: Path):
        db_path = tmp_path / "test3.db"
        monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from server.db import session_scope
        with session_scope() as session:  # noqa: F841
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_session_scope_rollback_on_error(self, monkeypatch, tmp_path: Path):
        db_path = tmp_path / "test4.db"
        monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from server.db import session_scope
        with pytest.raises(RuntimeError):
            with session_scope() as session:  # noqa: F841
                raise RuntimeError("rollback test")
