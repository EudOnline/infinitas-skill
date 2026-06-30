from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from server.db import _engine_kwargs


class TestEngineKwargs:
    def test_sqlite_returns_check_same_thread_false(self):
        kwargs = _engine_kwargs("sqlite:///test.db")
        assert kwargs["connect_args"] == {"check_same_thread": False}
        assert kwargs["poolclass"] is StaticPool

    def test_non_sqlite_returns_pool_settings(self):
        kwargs = _engine_kwargs("postgresql://user:pass@localhost/db")
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 3600


class TestGetDb:
    def test_get_db_yields_session(self, monkeypatch, tmp_path: Path):
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-32chars-long-minimum")
        monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        from server.settings import get_settings

        get_settings.cache_clear()
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
        monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-32chars-long-minimum")
        monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
        monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
        monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

        from server.db import get_engine, get_session_factory
        from server.settings import get_settings

        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        from server.db import get_db

        gen = get_db()
        session = next(gen)  # noqa: F841
        # Simulate an exception
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("test error"))
