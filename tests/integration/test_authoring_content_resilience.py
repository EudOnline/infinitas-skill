from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.model_base import utcnow
from tests.helpers.hosted_content import build_skill_bundle, upload_skill_content
from tests.integration.test_authoring_content_storage import configure_env

HEADERS = {"Authorization": "Bearer fixture-maintainer-token"}


def _client(tmp_path: Path, **overrides: str) -> TestClient:
    configure_env(tmp_path)
    for key, value in overrides.items():
        os.environ[key] = value
    from server.app import create_app

    return TestClient(create_app())


def _create_skill(client: TestClient, slug: str = "resilient-content") -> int:
    response = client.post(
        "/api/v1/skills",
        headers=HEADERS,
        json={"slug": slug, "display_name": "Resilient Content"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_pending_count_quota_frees_after_content_is_consumed(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        INFINITAS_SERVER_CONTENT_MAX_PENDING_PER_SKILL="1",
    )
    skill_id = _create_skill(client)
    first = upload_skill_content(client, skill_id, "resilient-content", "1.0.0", HEADERS)

    rejected = client.post(
        f"/api/v1/skills/{skill_id}/content",
        headers={**HEADERS, "Content-Type": "application/gzip"},
        content=build_skill_bundle("resilient-content", "1.0.1"),
    )
    assert rejected.status_code == 429
    assert rejected.json()["detail"] == "skill pending content quota exceeded"

    version = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=HEADERS,
        json={"version": "1.0.0", "content_id": first["content_id"]},
    )
    assert version.status_code == 201, version.text
    second = upload_skill_content(client, skill_id, "resilient-content", "1.0.1", HEADERS)
    assert second["declared_version"] == "1.0.1"


def test_pending_byte_quota_rejects_before_writing_artifacts(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        INFINITAS_SERVER_CONTENT_MAX_PENDING_BYTES_PER_PRINCIPAL="1",
    )
    skill_id = _create_skill(client)

    response = client.post(
        f"/api/v1/skills/{skill_id}/content",
        headers={**HEADERS, "Content-Type": "application/gzip"},
        content=build_skill_bundle("resilient-content", "1.0.0"),
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "publisher pending content byte quota exceeded"
    assert not any((tmp_path / "artifacts").rglob("*.tar.gz"))


def test_expired_content_is_rejected_and_pruned_on_next_upload(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        INFINITAS_SERVER_CONTENT_PENDING_TTL_HOURS="1",
    )
    skill_id = _create_skill(client)
    first = upload_skill_content(client, skill_id, "resilient-content", "1.0.0", HEADERS)

    from server.db import get_session_factory
    from server.modules.authoring.models import SkillContent

    with get_session_factory()() as session:
        content = session.scalar(
            select(SkillContent).where(SkillContent.public_id == first["content_id"])
        )
        assert content is not None
        content.created_at = utcnow() - timedelta(hours=2)
        old_storage_uri = content.storage_uri
        session.add(content)
        session.commit()

    expired = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=HEADERS,
        json={"version": "1.0.0", "content_id": first["content_id"]},
    )
    assert expired.status_code == 409
    assert expired.json()["detail"] == "validated skill content has expired"

    upload_skill_content(client, skill_id, "resilient-content", "1.0.1", HEADERS)

    with get_session_factory()() as session:
        content = session.scalar(
            select(SkillContent).where(SkillContent.public_id == first["content_id"])
        )
        assert content is not None and content.state == "expired"
    assert not (tmp_path / "artifacts" / "version-content" / first["content_id"]).exists()
    assert not (tmp_path / "artifacts" / old_storage_uri).exists()


def test_outer_transaction_failure_removes_new_files(monkeypatch, tmp_path: Path) -> None:
    client = _client(tmp_path)
    skill_id = _create_skill(client)
    original_commit = Session.commit
    failed = False

    def fail_first_commit(session: Session) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("forced outer commit failure")
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_first_commit)
    with pytest.raises(RuntimeError, match="forced outer commit failure"):
        upload_skill_content(client, skill_id, "resilient-content", "1.0.0", HEADERS)

    artifact_root = tmp_path / "artifacts"
    assert not any(path.is_file() for path in artifact_root.rglob("*"))


def test_worker_prunes_expired_pending_content(monkeypatch, tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        INFINITAS_SERVER_CONTENT_PENDING_TTL_HOURS="1",
    )
    skill_id = _create_skill(client)
    content_payload = upload_skill_content(client, skill_id, "resilient-content", "1.0.0", HEADERS)

    from server.db import get_session_factory
    from server.jobs import enqueue_job
    from server.modules.authoring.models import SkillContent
    from server.modules.jobs.models import Job
    from server.worker import run_worker_loop

    with get_session_factory()() as session:
        content = session.scalar(
            select(SkillContent).where(SkillContent.public_id == content_payload["content_id"])
        )
        assert content is not None
        content.created_at = utcnow() - timedelta(hours=2)
        session.add(content)
        enqueue_job(
            session,
            kind="prune_skill_contents",
            payload={"limit": 100},
            requested_by=None,
        )
        session.commit()

    assert run_worker_loop(limit=1) == 1

    with get_session_factory()() as session:
        content = session.scalar(
            select(SkillContent).where(SkillContent.public_id == content_payload["content_id"])
        )
        job = session.scalar(select(Job).where(Job.kind == "prune_skill_contents"))
        assert content is not None and content.state == "expired"
        assert job is not None and job.status == "completed"
