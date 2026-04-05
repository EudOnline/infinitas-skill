from __future__ import annotations

import json
import subprocess
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from infinitas_skill.install.distribution import verify_distribution_manifest
from server.models import Job, utcnow
from tests.helpers.signing import add_allowed_signer, configure_git_ssh_signing


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _prepare_signing_repo(repo: Path, signing_key: Path) -> None:
    allowed_signers = repo / "config" / "allowed_signers"
    allowed_signers.write_text("", encoding="utf-8")
    add_allowed_signer(allowed_signers, identity="release-test", key_path=signing_key)

    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.name", "Release Test"], cwd=repo)
    _run(["git", "config", "user.email", "release@example.com"], cwd=repo)
    configure_git_ssh_signing(repo, signing_key)
    _run(["git", "add", "config/allowed_signers", "config/signing.json"], cwd=repo)
    _run(["git", "commit", "-m", "test: bootstrap signing config"], cwd=repo)


def _configure_env(monkeypatch, *, tmp_path: Path, repo: Path) -> Path:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(artifact_root))
    monkeypatch.setenv("INFINITAS_SERVER_REPO_PATH", str(repo))
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        json.dumps(
            [
                {
                    "username": "fixture-maintainer",
                    "display_name": "Fixture Maintainer",
                    "role": "maintainer",
                    "token": "fixture-maintainer-token",
                }
            ]
        ),
    )
    return artifact_root


def _create_release(client: TestClient) -> int:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_skill = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "materialized-release",
            "display_name": "Materialized Release",
            "summary": "Hosted release materialization fixture",
        },
    )
    assert create_skill.status_code == 201, create_skill.text
    skill_id = int(create_skill.json()["id"])

    create_draft = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": "git+https://example.com/materialized-release.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": "materialized-release", "version": "0.1.0"},
            },
        },
    )
    assert create_draft.status_code == 201, create_draft.text
    draft_id = int(create_draft.json()["id"])

    seal = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int((seal.json().get("skill_version") or {})["id"])

    release = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert release.status_code == 201, release.text
    return int(release.json()["id"])


def _create_release_with_version(client: TestClient) -> tuple[int, int]:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_skill = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "materialized-release",
            "display_name": "Materialized Release",
            "summary": "Hosted release materialization fixture",
        },
    )
    assert create_skill.status_code == 201, create_skill.text
    skill_id = int(create_skill.json()["id"])

    create_draft = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": "git+https://example.com/materialized-release.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": "materialized-release", "version": "0.1.0"},
            },
        },
    )
    assert create_draft.status_code == 201, create_draft.text
    draft_id = int(create_draft.json()["id"])

    seal = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int((seal.json().get("skill_version") or {})["id"])

    release = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert release.status_code == 201, release.text
    return int(release.json()["id"]), version_id


def test_materialized_release_manifest_is_install_verifiable(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    artifact_root = _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id = _create_release(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    from server.db import get_session_factory

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.query(Job).filter(Job.release_id == release_id).order_by(Job.id.asc()).first()
        assert job is not None
        assert job.status == "completed"
        assert job.attempt_count == 1
        assert job.heartbeat_at is None
        assert job.lease_expires_at is None

    manifest_path = (
        artifact_root
        / "skills"
        / "fixture-maintainer"
        / "materialized-release"
        / "0.1.0"
        / "manifest.json"
    )
    assert manifest_path.exists(), f"missing manifest for release {release_id}"

    verified = verify_distribution_manifest(
        manifest_path,
        root=artifact_root,
        attestation_root=temp_repo_copy,
    )
    assert verified["verified"] is True


def test_repeat_release_request_requeues_legacy_ready_release_for_rematerialization(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    artifact_root = _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id, version_id = _create_release_with_version(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    manifest_path = (
        artifact_root
        / "skills"
        / "fixture-maintainer"
        / "materialized-release"
        / "0.1.0"
        / "manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "private-skill-release-manifest",
                "release_id": release_id,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    retry = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert retry.status_code == 200, retry.text

    processed = run_worker_loop(limit=1)
    assert processed == 1

    verified = verify_distribution_manifest(
        manifest_path,
        root=artifact_root,
        attestation_root=temp_repo_copy,
    )
    assert verified["verified"] is True


def test_repeat_release_request_can_recover_when_previous_materialization_job_is_stuck_running(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    artifact_root = _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app
    from server.db import get_session_factory
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id, version_id = _create_release_with_version(client)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.query(Job).filter(Job.release_id == release_id).order_by(Job.id.asc()).first()
        assert job is not None
        job.status = "running"
        job.started_at = utcnow() - timedelta(minutes=5)
        job.heartbeat_at = utcnow() - timedelta(minutes=5)
        job.lease_expires_at = utcnow() - timedelta(minutes=1)
        session.add(job)
        session.commit()

    retry = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert retry.status_code == 200, retry.text

    with session_factory() as session:
        jobs = (
            session.query(Job)
            .filter(Job.release_id == release_id)
            .order_by(Job.id.asc())
            .all()
        )
        assert [job.status for job in jobs] == ["running", "queued"]

    processed = run_worker_loop(limit=1)
    assert processed == 1

    manifest_path = (
        artifact_root
        / "skills"
        / "fixture-maintainer"
        / "materialized-release"
        / "0.1.0"
        / "manifest.json"
    )
    verified = verify_distribution_manifest(
        manifest_path,
        root=artifact_root,
        attestation_root=temp_repo_copy,
    )
    assert verified["verified"] is True


def test_repeat_release_request_does_not_duplicate_materialization_job_with_active_lease(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app
    from server.db import get_session_factory

    client = TestClient(create_app())
    release_id, version_id = _create_release_with_version(client)

    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.query(Job).filter(Job.release_id == release_id).order_by(Job.id.asc()).first()
        assert job is not None
        job.status = "running"
        job.started_at = utcnow() - timedelta(minutes=1)
        job.heartbeat_at = utcnow()
        job.lease_expires_at = utcnow() + timedelta(minutes=5)
        session.add(job)
        session.commit()

    retry = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert retry.status_code == 200, retry.text

    with session_factory() as session:
        jobs = (
            session.query(Job)
            .filter(Job.release_id == release_id)
            .order_by(Job.id.asc())
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].status == "running"
