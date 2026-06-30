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

    object_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "demo-published-skill",
            "display_name": "Demo Published Skill",
            "summary": "Published through the authoring/release flow",
        },
    )
    assert object_response.status_code == 201, object_response.text
    object_payload = object_response.json()
    object_id = object_payload["id"]
    assert object_payload["slug"] == "demo-published-skill"

    draft_response = client.post(
        f"/api/v1/skills/{object_id}/drafts",
        headers=headers,
        json={
            "content_ref": "git+https://example.com/demo.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert draft_response.status_code == 201, draft_response.text
    draft_id = draft_response.json()["id"]

    seal_response = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "1.2.3"},
    )
    assert seal_response.status_code == 201, seal_response.text
    version_id = seal_response.json()["skill_version"]["id"]

    release_response = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert release_response.status_code == 201, release_response.text
    release_payload = release_response.json()
    release_id = release_payload["id"]
    assert release_payload["skill_version_id"] == version_id
    assert "state" in release_payload

    from server.db import get_session_factory
    from server.modules.authoring.models import SkillVersion
    from server.modules.release.models import Release

    session_factory = get_session_factory()
    with session_factory() as session:
        release = session.get(Release, release_id)
        assert release is not None
        skill_version = session.get(SkillVersion, int(release.skill_version_id))
        assert skill_version is not None
        assert skill_version.created_from_draft_id is not None

    status = client.get(
        f"/api/v1/releases/{release_id}",
        headers=headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["id"] == release_id

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
