"""Shared test helpers for integration tests that need a library client with skill data."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _publish_skill_release(client, *, headers: dict) -> int:
    """Create a skill via the publish API and return its object ID."""
    object_response = client.put(
        "/api/v1/publish/objects/test-library-skill",
        headers=headers,
        json={
            "display_name": "Test Library Skill",
            "summary": "A skill for integration testing",
        },
    )
    assert object_response.status_code == 200, object_response.text
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

    from server.worker import run_worker_loop

    release_response = client.post(
        f"/api/v1/publish/objects/{skill_id}/releases",
        headers=headers,
        json={
            "version": "1.0.0",
            "content_ref": "git+https://example.com/test.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert release_response.status_code == 201, release_response.text
    run_worker_loop(limit=1)

    return client
