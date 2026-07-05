from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "fixture-maintainer",
                "display_name": "Fixture Maintainer",
                "role": "maintainer",
                "token": "fixture-maintainer-token",
            }
        ]
    )


def _canonical_metadata_json(metadata: dict) -> str:
    return json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _build_uploaded_bundle() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        entries = {
            "uploaded-skill/SKILL.md": b"# Uploaded Skill\n",
            "uploaded-skill/_meta.json": (
                json.dumps(
                    {
                        "name": "uploaded-skill",
                        "version": "0.1.0",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
        }
        for path, data in entries.items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _stage_uploaded_content_artifact(app_client: TestClient, *, artifact_root: Path) -> int:
    from server.db import get_session_factory
    from server.modules.release.models import Artifact
    from server.modules.release.storage import build_artifact_storage

    storage = build_artifact_storage(artifact_root)
    stored = storage.put_bytes(
        _build_uploaded_bundle(),
        public_path="version-content/uploaded-skill-0.1.0.tar.gz",
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        artifact = Artifact(
            release_id=None,
            kind="version_content",
            storage_uri=stored.storage_uri,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        return int(artifact.id)


def _create_skill(client: TestClient) -> int:
    response = client.post(
        "/api/v1/skills",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
        json={
            "slug": "uploaded-skill",
            "display_name": "Uploaded Skill",
            "summary": "content storage fixture",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_create_version_accepts_uploaded_content_bundle_reference() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-uploaded-content-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
        artifact_id = _stage_uploaded_content_artifact(client, artifact_root=tmpdir / "artifacts")
        skill_id = _create_skill(client)

        response = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers={"Authorization": "Bearer fixture-maintainer-token"},
            json={
                "version": "0.1.0",
                "content_mode": "uploaded_bundle",
                "content_upload_token": str(artifact_id),
                "metadata": {
                    "entrypoint": "SKILL.md",
                    "manifest": {"name": "uploaded-skill", "version": "0.1.0"},
                },
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["sealed_manifest"]["content_mode"] == "uploaded_bundle"
        assert payload["sealed_manifest"]["content_artifact_id"] == artifact_id
        assert payload["sealed_manifest"]["content_ref"] == ""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_create_version_accepts_external_immutable_content_ref() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-external-content-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
        skill_id = _create_skill(client)

        response = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers={"Authorization": "Bearer fixture-maintainer-token"},
            json={
                "version": "0.1.0",
                "content_mode": "external_ref",
                "content_ref": "git+https://example.com/uploaded-skill.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        expected_ref = "#0123456789abcdef0123456789abcdef01234567"
        assert payload["sealed_manifest"]["content_mode"] == "external_ref"
        assert payload["sealed_manifest"]["content_artifact_id"] is None
        assert payload["sealed_manifest"]["content_ref"].endswith(expected_ref)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_create_version_freezes_content_and_metadata_digests() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-seal-content-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
        artifact_id = _stage_uploaded_content_artifact(client, artifact_root=tmpdir / "artifacts")
        skill_id = _create_skill(client)
        metadata = {
            "entrypoint": "SKILL.md",
            "manifest": {"name": "uploaded-skill", "version": "0.1.0"},
        }

        response = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers={"Authorization": "Bearer fixture-maintainer-token"},
            json={
                "version": "0.1.0",
                "content_mode": "uploaded_bundle",
                "content_upload_token": str(artifact_id),
                "metadata": metadata,
            },
        )
        assert response.status_code == 201, response.text

        payload = response.json()
        assert payload["content_digest"].startswith("sha256:")
        assert payload["metadata_digest"].startswith("sha256:")
        assert payload["sealed_manifest"]["content_mode"] == "uploaded_bundle"
        assert payload["sealed_manifest"]["content_artifact_id"] == artifact_id
        assert payload["sealed_manifest"]["metadata"] == metadata
        assert payload["metadata_digest"] != payload["content_digest"]
        assert _canonical_metadata_json(metadata) in payload["sealed_manifest_json"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
