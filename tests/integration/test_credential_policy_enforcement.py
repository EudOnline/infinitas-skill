from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.helpers.hosted_content import build_skill_bundle, upload_skill_content
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)

HEADERS = {"Authorization": "Bearer fixture-maintainer-token"}


def _client(monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path) -> TestClient:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app

    return TestClient(create_app())


def _credential_id(client: TestClient) -> int:
    response = client.get("/api/v1/profile/me", headers=HEADERS)
    assert response.status_code == 200, response.text
    return int(response.json()["identity"]["credential_id"])


def _set_policy(client: TestClient, payload: dict) -> None:
    response = client.patch(
        f"/api/v1/credentials/{_credential_id(client)}/policy",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 200, response.text


def _create_skill(client: TestClient, slug: str) -> int:
    response = client.post(
        "/api/v1/skills",
        headers=HEADERS,
        json={"slug": slug, "display_name": slug.replace("-", " ").title()},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _create_version(client: TestClient, skill_id: int, slug: str, version: str) -> int:
    content = upload_skill_content(client, skill_id, slug, version, HEADERS)
    response = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=HEADERS,
        json={"version": version, "content_id": content["content_id"]},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_readonly_policy_blocks_every_agent_authoring_mutation(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    skill_id = _create_skill(client, "readonly-skill")
    release_version_id = _create_version(client, skill_id, "readonly-skill", "1.0.0")
    pending_content = upload_skill_content(client, skill_id, "readonly-skill", "1.0.1", HEADERS)
    _set_policy(client, {"readonly": True})

    create_skill = client.post(
        "/api/v1/skills",
        headers=HEADERS,
        json={"slug": "blocked-skill", "display_name": "Blocked Skill"},
    )
    upload = client.post(
        f"/api/v1/skills/{skill_id}/content",
        headers={**HEADERS, "Content-Type": "application/gzip"},
        content=build_skill_bundle("readonly-skill", "1.0.2"),
    )
    create_version = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=HEADERS,
        json={"version": "1.0.1", "content_id": pending_content["content_id"]},
    )
    create_release = client.post(
        f"/api/v1/versions/{release_version_id}/releases",
        headers=HEADERS,
    )

    for response in (create_skill, upload, create_version, create_release):
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "credential is read-only"


def test_allowed_object_kinds_policy_blocks_skill_authoring(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    _set_policy(client, {"allowed_object_kinds": []})

    response = client.post(
        "/api/v1/skills",
        headers=HEADERS,
        json={"slug": "disallowed-skill", "display_name": "Disallowed Skill"},
    )

    assert response.status_code == 403
    assert "does not allow object kind" in response.json()["detail"]


def test_daily_publish_limit_is_atomic_and_rolls_back_rejected_release(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    skill_id = _create_skill(client, "quota-skill")
    first_version = _create_version(client, skill_id, "quota-skill", "1.0.0")
    second_version = _create_version(client, skill_id, "quota-skill", "1.0.1")
    _set_policy(client, {"max_daily_publishes": 1})

    first = client.post(f"/api/v1/versions/{first_version}/releases", headers=HEADERS)
    repeated = client.post(f"/api/v1/versions/{first_version}/releases", headers=HEADERS)
    rejected = client.post(f"/api/v1/versions/{second_version}/releases", headers=HEADERS)

    assert first.status_code == 201, first.text
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["id"] == first.json()["id"]
    assert rejected.status_code == 429, rejected.text
    assert int(rejected.headers["retry-after"]) > 0

    from server.db import get_session_factory
    from server.modules.jobs.models import Job
    from server.modules.release.models import Release

    with get_session_factory()() as session:
        assert (
            session.scalar(
                select(func.count(Release.id)).where(Release.skill_version_id == second_version)
            )
            == 0
        )
        assert session.scalar(select(func.count(Job.id))) == 1


def test_policy_update_is_visible_and_audited(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    credential_id = _credential_id(client)
    _set_policy(client, {"max_daily_publishes": 3, "readonly": False})

    profile = client.get("/api/v1/profile/me", headers=HEADERS)
    assert profile.json()["policy"] == {"max_daily_publishes": 3, "readonly": False}

    from server.db import get_session_factory
    from server.modules.audit.models import AuditEvent

    with get_session_factory()() as session:
        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "credential")
            .where(AuditEvent.aggregate_id == str(credential_id))
            .where(AuditEvent.event_type == "credential.policy.updated")
        )
        assert event is not None
        assert event.actor_ref.startswith("user:")
