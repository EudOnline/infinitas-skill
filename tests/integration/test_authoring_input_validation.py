from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
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


def test_create_skill_rejects_invalid_slug() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-slug-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        response = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "Bad/Slug",
                "display_name": "Bad Slug",
                "summary": "invalid slug fixture",
            },
        )
        assert response.status_code == 422, response.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_seal_draft_rejects_invalid_version_string() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-authoring-version-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        create_skill = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "valid-skill",
                "display_name": "Valid Skill",
                "summary": "valid fixture",
            },
        )
        assert create_skill.status_code == 201, create_skill.text
        skill_id = int(create_skill.json()["id"])

        create_draft = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "content_ref": "git+https://example.com/valid-skill.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        assert create_draft.status_code == 201, create_draft.text
        draft_id = int(create_draft.json()["id"])

        seal_response = client.post(
            f"/api/v1/drafts/{draft_id}/seal",
            headers=headers,
            json={"version": "release/1"},
        )
        assert seal_response.status_code == 422, seal_response.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
