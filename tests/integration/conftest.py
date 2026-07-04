"""Shared test helpers for integration tests that need a library client with skill data."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _publish_skill_release(client, *, headers: dict) -> int:
    """Create a skill via the authoring API and return its object ID."""
    object_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "test-library-skill",
            "display_name": "Test Library Skill",
            "summary": "A skill for integration testing",
        },
    )
    assert object_response.status_code == 201, object_response.text
    return object_response.json()["id"]


def _prepare_library_client(
    monkeypatch,
    *,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> TestClient:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)

    from server.app import create_app

    client = TestClient(create_app())

    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    skill_id = _publish_skill_release(client, headers=headers)

    version_response = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=headers,
        json={
            "version": "1.0.0",
            "content_ref": "git+https://example.com/test.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert version_response.status_code == 201, version_response.text
    version_id = version_response.json()["id"]

    from server.worker import run_worker_loop

    release_response = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert release_response.status_code == 201, release_response.text
    run_worker_loop(limit=1)

    return client
