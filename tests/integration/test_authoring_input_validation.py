from __future__ import annotations

import json
import os
import shutil
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


def test_create_version_rejects_invalid_version_string() -> None:
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

        create_version = client.post(
            f"/api/v1/skills/{skill_id}/versions",
            headers=headers,
            json={
                "version": "release/1",
                "content_id": "cnt_validationfixture",
            },
        )
        assert create_version.status_code == 422, create_version.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
