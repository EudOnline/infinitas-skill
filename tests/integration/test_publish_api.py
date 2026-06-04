from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from infinitas_skill.install.distribution import verify_distribution_manifest
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _client(
    monkeypatch,
    *,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> TestClient:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app

    return TestClient(create_app())


def test_publish_facade_creates_release_without_draft_or_seal_terms(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    object_response = client.put(
        "/api/v1/publish/objects/demo-published-skill",
        headers=headers,
        json={
            "display_name": "Demo Published Skill",
            "summary": "Published through the product facade",
        },
    )
    assert object_response.status_code == 200, object_response.text
    object_payload = object_response.json()
    object_id = object_payload["id"]
    assert object_payload["kind"] == "skill"

    release_response = client.post(
        f"/api/v1/publish/objects/{object_id}/releases",
        headers=headers,
        json={
            "version": "1.2.3",
            "content_ref": "git+https://example.com/demo.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert release_response.status_code == 201, release_response.text
    release_payload = release_response.json()
    assert release_payload["object_id"] == object_id
    assert release_payload["object_kind"] == "skill"
    assert release_payload["version"] == "1.2.3"
    assert "draft" not in release_payload
    assert "seal" not in release_payload

    from server.db import get_session_factory
    from server.models import SkillDraft, SkillVersion
    from server.modules.release.models import Release

    session_factory = get_session_factory()
    with session_factory() as session:
        release = session.get(Release, int(release_payload["release_id"]))
        assert release is not None
        skill_version = session.get(SkillVersion, int(release.skill_version_id))
        assert skill_version is not None
        assert skill_version.created_from_draft_id is None
        assert session.query(SkillDraft).count() == 0

    status = client.get(
        f"/api/v1/publish/releases/{release_payload['release_id']}/status",
        headers=headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["release_id"] == release_payload["release_id"]

    from server.worker import run_worker_loop

    assert run_worker_loop(limit=1) == 1
    manifest_path = (
        tmp_path
        / "artifacts"
        / "skills"
        / "fixture-maintainer"
        / "demo-published-skill"
        / "1.2.3"
        / "manifest.json"
    )
    assert manifest_path.exists()
    verified = verify_distribution_manifest(
        manifest_path,
        root=tmp_path / "artifacts",
        attestation_root=temp_repo_copy,
    )
    assert verified["verified"] is True
