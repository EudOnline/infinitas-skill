from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers.hosted_content import upload_skill_content
from tests.integration.conftest import _prepare_library_client

HEADERS = {"Authorization": "Bearer fixture-maintainer-token"}


def _prepared_client(
    monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path
) -> tuple[TestClient, int, dict]:
    client = _prepare_library_client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    skill = client.get("/api/v1/skills?slug=test-library-skill", headers=HEADERS).json()[0]
    version = client.get(f"/api/v1/skills/{skill['id']}/versions", headers=HEADERS).json()[0]
    return client, int(skill["id"]), version


def _create_change_set(
    client: TestClient,
    skill_id: int,
    base_version_id: int,
    version: str,
) -> dict:
    content = upload_skill_content(client, skill_id, "test-library-skill", version, HEADERS)
    response = client.post(
        f"/api/v1/skills/{skill_id}/changesets",
        headers=HEADERS,
        json={
            "base_version_id": base_version_id,
            "content_id": content["content_id"],
            "proposed_version": version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_competing_agent_change_sets_allow_one_promotion_and_supersede_the_other(
    monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path
) -> None:
    client, skill_id, base = _prepared_client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    first = _create_change_set(client, skill_id, base["id"], "1.1.0")
    second = _create_change_set(client, skill_id, base["id"], "1.2.0")
    for change_set in (first, second):
        response = client.post(
            f"/api/v1/skills/{skill_id}/changesets/{change_set['id']}/submit",
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text

    accepted = client.post(
        f"/api/v1/skills/{skill_id}/changesets/{first['id']}/accept",
        headers=HEADERS,
        json={"expected_latest_digest": base["content_digest"]},
    )

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["change_set"]["state"] == "accepted"
    assert accepted.json()["version"] == "1.1.0"
    superseded = client.get(f"/api/v1/skills/{skill_id}/changesets/{second['id']}", headers=HEADERS)
    assert superseded.json()["state"] == "superseded"
    rejected = client.post(
        f"/api/v1/skills/{skill_id}/changesets/{second['id']}/accept",
        headers=HEADERS,
        json={"expected_latest_digest": base["content_digest"]},
    )
    assert rejected.status_code == 409
    assert len(client.get(f"/api/v1/skills/{skill_id}/versions", headers=HEADERS).json()) == 2


def test_change_set_rejects_stale_expected_digest_without_consuming_content(
    monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path
) -> None:
    client, skill_id, base = _prepared_client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    change_set = _create_change_set(client, skill_id, base["id"], "1.1.0")
    client.post(
        f"/api/v1/skills/{skill_id}/changesets/{change_set['id']}/submit",
        headers=HEADERS,
    )

    response = client.post(
        f"/api/v1/skills/{skill_id}/changesets/{change_set['id']}/accept",
        headers=HEADERS,
        json={"expected_latest_digest": "sha256:" + "0" * 64},
    )

    assert response.status_code == 409
    current = client.get(
        f"/api/v1/skills/{skill_id}/changesets/{change_set['id']}", headers=HEADERS
    ).json()
    assert current["state"] == "submitted"


def test_encrypted_data_snapshot_registration_preserves_lineage_and_audit_metadata(
    monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path
) -> None:
    client, skill_id, version = _prepared_client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    common = {
        "skill_version_id": version["id"],
        "schema_version": 1,
        "ciphertext_sha256": "sha256:" + "a" * 64,
        "ciphertext_size_bytes": 1234,
        "manifest_digest": "sha256:" + "b" * 64,
        "encryption": "age",
    }
    first_response = client.post(
        f"/api/v1/skills/{skill_id}/data-snapshots",
        headers=HEADERS,
        json={
            **common,
            "encrypted_object_uri": "openlist://skill-backups/first.tar.gz.age",
        },
    )
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    duplicate = client.post(
        f"/api/v1/skills/{skill_id}/data-snapshots",
        headers=HEADERS,
        json={
            **common,
            "encrypted_object_uri": "openlist://skill-backups/duplicate.tar.gz.age",
        },
    )
    assert duplicate.status_code == 409
    second_response = client.post(
        f"/api/v1/skills/{skill_id}/data-snapshots",
        headers=HEADERS,
        json={
            **common,
            "parent_snapshot_id": first["id"],
            "encrypted_object_uri": "openlist://skill-backups/second.tar.gz.age",
            "ciphertext_sha256": "sha256:" + "c" * 64,
        },
    )
    assert second_response.status_code == 201, second_response.text
    assert second_response.json()["parent_snapshot_id"] == first["id"]
    listed = client.get(f"/api/v1/skills/{skill_id}/data-snapshots", headers=HEADERS).json()
    assert [item["id"] for item in listed] == [second_response.json()["id"], first["id"]]

    from server.db import get_session_factory
    from server.modules.audit.models import AuditEvent

    with get_session_factory()() as db:
        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.aggregate_id == second_response.json()["id"])
            .one()
        )
    audit_payload = json.loads(event.payload_json)
    assert audit_payload["ciphertext_sha256"] == "sha256:" + "c" * 64
    assert "encrypted_object_uri" not in audit_payload


def test_data_snapshot_registration_rejects_plaintext_or_credential_bearing_uri(
    monkeypatch, tmp_path: Path, temp_repo_copy: Path, signing_key: Path
) -> None:
    client, skill_id, version = _prepared_client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    base = {
        "skill_version_id": version["id"],
        "schema_version": 1,
        "ciphertext_sha256": "sha256:" + "a" * 64,
        "ciphertext_size_bytes": 1,
        "manifest_digest": "sha256:" + "b" * 64,
    }
    for uri in (
        "https://user:password@example.test/snapshot.tar.gz.age",
        "https://example.test/snapshot.tar.gz",
    ):
        response = client.post(
            f"/api/v1/skills/{skill_id}/data-snapshots",
            headers=HEADERS,
            json={**base, "encrypted_object_uri": uri},
        )
        assert response.status_code == 422
