from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_library_api import _prepare_library_client


def _prepared_object_and_release(
    client: TestClient,
    *,
    headers: dict[str, str],
) -> tuple[int, int]:
    listing = client.get("/api/library", headers=headers)
    assert listing.status_code == 200, listing.text
    skill_object = next(item for item in listing.json()["items"] if item["kind"] == "skill")
    object_id = int(skill_object["id"])
    release_id = int(skill_object["current_release"]["release_id"])

    grant_exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": "grant",
            "listing_mode": "direct_only",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert grant_exposure.status_code == 201, grant_exposure.text
    return object_id, release_id


def test_create_reader_token_for_release_returns_raw_token_once(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _prepare_library_client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    object_id, release_id = _prepared_object_and_release(client, headers=headers)

    response = client.post(
        f"/api/objects/{object_id}/tokens",
        headers=headers,
        json={
            "name": "reader-a",
            "type": "reader",
            "scope_type": "release",
            "scope_id": release_id,
            "issued_for": "agent-a",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["raw_token"].startswith("tok_")
    assert created["token"]["name"] == "reader-a"
    assert created["token"]["type"] == "reader"
    assert created["token"]["scope_type"] == "release"
    assert created["token"]["scope_id"] == release_id
    assert created["token"]["state"] == "active"

    listing = client.get(f"/api/objects/{object_id}/tokens", headers=headers)
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "reader-a"
    assert "raw_token" not in payload["items"][0]


def test_create_publisher_token_for_object_and_revoke(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _prepare_library_client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    object_id, _release_id = _prepared_object_and_release(client, headers=headers)

    response = client.post(
        f"/api/objects/{object_id}/tokens",
        headers=headers,
        json={
            "name": "publisher-a",
            "type": "publisher",
            "scope_type": "object",
            "scope_id": object_id,
            "expires_in_days": 30,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    assert token["type"] == "publisher"
    assert token["scope_type"] == "object"
    assert token["scope_id"] == object_id
    assert token["expires_at"] is not None

    revoke = client.post(f"/api/tokens/{token['id']}/revoke", headers=headers)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["state"] == "revoked"

    listing = client.get(f"/api/objects/{object_id}/tokens", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["state"] == "revoked"
