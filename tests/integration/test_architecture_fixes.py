"""Tests for architecture fixes: N+1, exception handling, rate limiting, cache busting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from server.db import _engine_kwargs
from server.modules.access.authn import AccessContext
from server.modules.access.authz import can_access_releases
from server.modules.access.models import AccessGrant
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.identity.models import Credential, Principal, User
from server.modules.release.models import Release
from server.rate_limit import DBRateLimiter, MemoryRateLimiter
from server.ui.assets import load_asset_hashes, static_url_factory


@pytest.fixture
def db(monkeypatch, tmp_path: Path):
    """Yield a managed SQLAlchemy session for tests."""
    db_path = tmp_path / "arch_fixes.db"
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-arch-fixes-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
    monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["localhost","testserver"]')

    from server.db import get_engine, get_session_factory
    from server.lifecycle import ensure_database_ready

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    ensure_database_ready()

    with get_session_factory()() as session:
        yield session


class TestBatchCanAccessReleases:
    """Verify the batch variant avoids N+1 while preserving correctness."""

    def test_empty_list_returns_empty_set(self, db: Session):
        cred = Credential(
            type="personal_token",
            hashed_secret="sha256:abc",
            scopes_json='["api:user"]',
        )
        db.add(cred)
        db.flush()
        principal = Principal(kind="user", slug="test", display_name="Test")
        db.add(principal)
        db.flush()
        context = AccessContext(
            credential=cred, principal=principal, user=None, scopes={"api:user"}
        )
        assert can_access_releases(db, context=context, release_ids=[]) == set()

    def test_public_exposure_is_accessible(self, db: Session):
        principal = Principal(kind="user", slug="pub", display_name="Pub")
        db.add(principal)
        db.flush()
        user = User(username="pub", display_name="Pub", role="contributor")
        db.add(user)
        db.flush()

        skill = Skill(namespace_id=principal.id, slug="test-skill", display_name="Test")
        db.add(skill)
        db.flush()
        sv = SkillVersion(
            skill_id=skill.id,
            version="1.0.0",
            content_digest="digest1",
            metadata_digest="digest2",
            sealed_manifest_json="{}",
        )
        db.add(sv)
        db.flush()
        release = Release(
            skill_version_id=sv.id,
            skill_id=skill.id,
            state="ready",
            format_version="1",
            created_by_principal_id=principal.id,
        )
        db.add(release)
        db.flush()
        exposure = Exposure(
            release_id=release.id,
            audience_type="public",
            listing_mode="listed",
            install_mode="enabled",
            review_requirement="none",
            state="active",
        )
        db.add(exposure)
        db.commit()

        cred = Credential(
            type="personal_token",
            principal_id=principal.id,
            hashed_secret="sha256:abc",
            scopes_json='["api:user"]',
        )
        db.add(cred)
        db.commit()

        context = AccessContext(
            credential=cred, principal=principal, user=user, scopes={"api:user"}
        )
        assert can_access_releases(db, context=context, release_ids=[release.id]) == {release.id}

    def test_grant_without_matching_principal_is_denied(self, db: Session):
        principal = Principal(kind="user", slug="deny", display_name="Deny")
        db.add(principal)
        db.flush()
        user = User(username="deny", display_name="Deny", role="contributor")
        db.add(user)
        db.flush()

        skill = Skill(namespace_id=principal.id, slug="deny-skill", display_name="Deny")
        db.add(skill)
        db.flush()
        sv = SkillVersion(
            skill_id=skill.id,
            version="1.0.0",
            content_digest="digest1",
            metadata_digest="digest2",
            sealed_manifest_json="{}",
        )
        db.add(sv)
        db.flush()
        release = Release(
            skill_version_id=sv.id,
            skill_id=skill.id,
            state="ready",
            format_version="1",
            created_by_principal_id=principal.id,
        )
        db.add(release)
        db.flush()
        exposure = Exposure(
            release_id=release.id,
            audience_type="grant",
            listing_mode="listed",
            install_mode="enabled",
            review_requirement="none",
            state="active",
        )
        db.add(exposure)
        db.flush()

        other = Principal(kind="user", slug="other", display_name="Other")
        db.add(other)
        db.flush()
        grant = AccessGrant(
            exposure_id=exposure.id,
            grant_type="user",
            subject_ref=f"principal:{other.id}",
            state="active",
        )
        db.add(grant)
        db.commit()

        cred = Credential(
            type="personal_token",
            principal_id=principal.id,
            hashed_secret="sha256:abc",
            scopes_json='["api:user"]',
        )
        db.add(cred)
        db.commit()

        context = AccessContext(
            credential=cred, principal=principal, user=user, scopes={"api:user"}
        )
        assert can_access_releases(db, context=context, release_ids=[release.id]) == set()


class TestMemoryRateLimiter:
    def test_under_limit(self):
        limiter = MemoryRateLimiter()
        assert limiter.check("k", max_attempts=3, window_seconds=60) is True
        limiter.record("k")
        assert limiter.check("k", max_attempts=3, window_seconds=60) is True

    def test_over_limit(self):
        limiter = MemoryRateLimiter()
        for _ in range(3):
            limiter.record("k")
        assert limiter.check("k", max_attempts=3, window_seconds=60) is False

    def test_reset_clears_key(self):
        limiter = MemoryRateLimiter()
        limiter.record("k")
        assert limiter.check("k", max_attempts=1, window_seconds=60) is False
        limiter.reset("k")
        assert limiter.check("k", max_attempts=1, window_seconds=60) is True

    def test_reset_all_clears_everything(self):
        limiter = MemoryRateLimiter()
        limiter.record("a")
        limiter.record("b")
        limiter.reset_all()
        assert limiter.check("a", max_attempts=1, window_seconds=60) is True
        assert limiter.check("b", max_attempts=1, window_seconds=60) is True


class TestDBRateLimiter:
    def test_record_and_check(self, db: Session):
        limiter = DBRateLimiter(db)
        assert limiter.check("k", max_attempts=3, window_seconds=60) is True
        limiter.record("k")
        limiter.record("k")
        assert limiter.check("k", max_attempts=3, window_seconds=60) is True
        limiter.record("k")
        assert limiter.check("k", max_attempts=3, window_seconds=60) is False

    def test_reset(self, db: Session):
        limiter = DBRateLimiter(db)
        limiter.record("k")
        assert limiter.check("k", max_attempts=1, window_seconds=60) is False
        limiter.reset("k")
        assert limiter.check("k", max_attempts=1, window_seconds=60) is True

    def test_reset_all(self, db: Session):
        limiter = DBRateLimiter(db)
        limiter.record("a")
        limiter.record("b")
        limiter.reset_all()
        assert limiter.check("a", max_attempts=1, window_seconds=60) is True
        assert limiter.check("b", max_attempts=1, window_seconds=60) is True


class TestAssetHashHelpers:
    def test_load_missing_file(self, tmp_path: Path):
        assert load_asset_hashes(tmp_path) == {}

    def test_load_valid_manifest(self, tmp_path: Path):
        hashes = {"css/output.css": "abc123", "app.js": "def456"}
        (tmp_path / ".hashes.json").write_text(json.dumps(hashes))
        assert load_asset_hashes(tmp_path) == hashes

    def test_static_url_with_hash(self):
        url = static_url_factory({"css/output.css": "abc123"})("/static/css/output.css")
        assert url == "/static/css/output.css?v=abc123"

    def test_static_url_without_hash(self):
        url = static_url_factory({})("/static/css/output.css")
        assert url == "/static/css/output.css"


class TestEngineKwargs:
    def test_memory_sqlite_uses_static_pool(self):
        kwargs = _engine_kwargs("sqlite:///:memory:")
        from sqlalchemy.pool import StaticPool

        assert kwargs["poolclass"] is StaticPool
        assert kwargs["connect_args"] == {"check_same_thread": False}

    def test_postgresql_uses_pool_pre_ping(self):
        kwargs = _engine_kwargs("postgresql://user:pass@localhost/db")
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 3600
