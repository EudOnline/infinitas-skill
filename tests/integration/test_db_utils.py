from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from server.db import _engine_kwargs


def _configure_bootstrap_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(
        "INFINITAS_SERVER_DATABASE_URL",
        f"sqlite:///{tmp_path / 'bootstrap.db'}",
    )
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-32chars-long-minimum")
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "generated-token-user",
                    "display_name": "Generated Token User",
                    "role": "maintainer",
                }
            ]
        ),
    )

    from server.db import get_engine, get_session_factory
    from server.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


class TestEngineKwargs:
    def test_file_sqlite_returns_thread_and_pool_health_settings(self):
        kwargs = _engine_kwargs("sqlite:///test.db")
        assert kwargs["connect_args"] == {"check_same_thread": False}
        assert kwargs["pool_pre_ping"] is True
        assert "poolclass" not in kwargs

    def test_memory_sqlite_uses_static_pool(self):
        kwargs = _engine_kwargs("sqlite:///:memory:")
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


class TestBootstrapCredentials:
    def test_configured_password_rotates_when_bootstrap_value_changes(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        _configure_bootstrap_env(monkeypatch, tmp_path)
        first_payload = [
            {
                "username": "generated-token-user",
                "display_name": "Generated Token User",
                "role": "maintainer",
                "password": "FirstPass123!",
            }
        ]
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(first_payload))

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.models import User
        from server.modules.identity.passwords import verify_password
        from server.settings import get_settings

        get_settings.cache_clear()
        ensure_database_ready()

        with get_session_factory()() as session:
            user = session.query(User).filter(User.username == "generated-token-user").one()
            first_hash = user.password_hash
            assert verify_password("FirstPass123!", first_hash)

        first_payload[0]["password"] = "SecondPass456!"
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(first_payload))
        get_settings.cache_clear()
        ensure_database_ready()

        with get_session_factory()() as session:
            user = session.query(User).filter(User.username == "generated-token-user").one()
            assert user.password_hash != first_hash
            assert not verify_password("FirstPass123!", user.password_hash)
            assert verify_password("SecondPass456!", user.password_hash)

    def test_password_rotation_revokes_existing_browser_sessions(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        _configure_bootstrap_env(monkeypatch, tmp_path)
        payload = [
            {
                "username": "generated-token-user",
                "display_name": "Generated Token User",
                "role": "maintainer",
                "password": "FirstPass123!",
            }
        ]
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(payload))

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.models import Credential

        ensure_database_ready()
        with get_session_factory()() as session:
            principal_id = session.query(Credential).first().principal_id
            from server.modules.identity.service import create_fresh_session_credential

            session_credential = create_fresh_session_credential(session, principal_id=principal_id)
            session.commit()
            session_id = session_credential.id

        payload[0]["password"] = "SecondPass456!"
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(payload))
        from server.settings import get_settings

        get_settings.cache_clear()
        ensure_database_ready()

        with get_session_factory()() as session:
            assert session.get(Credential, session_id).revoked_at is not None

    def test_removed_bootstrap_user_is_disabled_and_credentials_revoked(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        _configure_bootstrap_env(monkeypatch, tmp_path)
        payload = [
            {
                "username": "generated-token-user",
                "display_name": "Generated Token User",
                "role": "maintainer",
                "password": "FirstPass123!",
                "token": "configured-agent-token",
            },
            {
                "username": "temporary-user",
                "display_name": "Temporary User",
                "role": "contributor",
                "password": "TemporaryPass123!",
                "token": "temporary-agent-token",
            },
        ]
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(payload))

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.models import Credential, User
        from server.modules.identity.service import resolve_credential_by_token
        from server.settings import get_settings

        get_settings.cache_clear()
        ensure_database_ready()
        with get_session_factory()() as session:
            temporary = session.query(User).filter(User.username == "temporary-user").one()
            credential = resolve_credential_by_token(session, "temporary-agent-token")
            assert credential is not None
            credential_id = credential.id
            assert temporary.password_hash is not None

        monkeypatch.setenv(
            "INFINITAS_SERVER_BOOTSTRAP_USERS",
            json.dumps([payload[0]]),
        )
        get_settings.cache_clear()
        ensure_database_ready()

        with get_session_factory()() as session:
            temporary = session.query(User).filter(User.username == "temporary-user").one()
            assert temporary.password_hash is None
            assert session.get(Credential, credential_id).revoked_at is not None
            assert resolve_credential_by_token(session, "temporary-agent-token") is None

    def test_unchanged_bootstrap_password_keeps_existing_hash(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        _configure_bootstrap_env(monkeypatch, tmp_path)
        payload = [
            {
                "username": "generated-token-user",
                "display_name": "Generated Token User",
                "role": "maintainer",
                "password": "StablePass123!",
            }
        ]
        monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(payload))

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.models import User
        from server.settings import get_settings

        get_settings.cache_clear()
        ensure_database_ready()
        with get_session_factory()() as session:
            first_hash = (
                session.query(User)
                .filter(User.username == "generated-token-user")
                .one()
                .password_hash
            )

        ensure_database_ready()
        with get_session_factory()() as session:
            second_hash = (
                session.query(User)
                .filter(User.username == "generated-token-user")
                .one()
                .password_hash
            )
        assert second_hash == first_hash

    def test_generated_token_is_stored_and_resolves(self, monkeypatch, tmp_path: Path):
        _configure_bootstrap_env(monkeypatch, tmp_path)
        monkeypatch.setattr(secrets, "token_urlsafe", lambda _size: "generated-token-value")

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.service import resolve_credential_by_token

        ensure_database_ready()

        with get_session_factory()() as session:
            credential = resolve_credential_by_token(
                session,
                "dev_generated-token-value",
            )
            assert credential is not None
            assert credential.type == "personal_token"
            assert credential.last_used_at is not None

    def test_generated_token_is_not_rotated_on_restart(self, monkeypatch, tmp_path: Path):
        _configure_bootstrap_env(monkeypatch, tmp_path)
        generated_values = iter(["first-token-value", "second-token-value"])
        monkeypatch.setattr(secrets, "token_urlsafe", lambda _size: next(generated_values))

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.service import resolve_credential_by_token

        ensure_database_ready()
        ensure_database_ready()

        with get_session_factory()() as session:
            assert resolve_credential_by_token(session, "dev_first-token-value") is not None
            assert resolve_credential_by_token(session, "dev_second-token-value") is None

    def test_session_rotation_preserves_personal_token(self, monkeypatch, tmp_path: Path):
        _configure_bootstrap_env(monkeypatch, tmp_path)
        monkeypatch.setenv(
            "INFINITAS_SERVER_BOOTSTRAP_USERS",
            json.dumps(
                [
                    {
                        "username": "generated-token-user",
                        "display_name": "Generated Token User",
                        "role": "maintainer",
                        "token": "configured-agent-token",
                    }
                ]
            ),
        )

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.modules.identity.service import (
            create_fresh_session_credential,
            resolve_credential_by_token,
        )

        ensure_database_ready()

        with get_session_factory()() as session:
            personal = resolve_credential_by_token(session, "configured-agent-token")
            assert personal is not None

            browser_session = create_fresh_session_credential(
                session,
                principal_id=personal.principal_id,
            )
            session.commit()

            assert browser_session.type == "session"
            assert resolve_credential_by_token(session, "configured-agent-token") is not None

    def test_configured_token_replaces_revoked_credential(self, monkeypatch, tmp_path: Path):
        _configure_bootstrap_env(monkeypatch, tmp_path)
        monkeypatch.setenv(
            "INFINITAS_SERVER_BOOTSTRAP_USERS",
            json.dumps(
                [
                    {
                        "username": "generated-token-user",
                        "display_name": "Generated Token User",
                        "role": "maintainer",
                        "token": "configured-agent-token",
                    }
                ]
            ),
        )

        from server.db import get_session_factory
        from server.lifecycle import ensure_database_ready
        from server.model_base import utcnow
        from server.modules.identity.service import resolve_credential_by_token

        ensure_database_ready()

        with get_session_factory()() as session:
            revoked = resolve_credential_by_token(session, "configured-agent-token")
            assert revoked is not None
            revoked_id = revoked.id
            revoked.revoked_at = utcnow()
            session.commit()

        ensure_database_ready()

        with get_session_factory()() as session:
            replacement = resolve_credential_by_token(session, "configured-agent-token")
            assert replacement is not None
            assert replacement.id != revoked_id
            assert session.get(type(replacement), revoked_id).revoked_at is not None
