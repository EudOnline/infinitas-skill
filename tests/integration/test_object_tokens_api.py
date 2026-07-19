from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers.hosted_content import upload_skill_content
from tests.integration.conftest import _prepare_library_client


def _prepared_object_and_release(
    client: TestClient,
    *,
    headers: dict[str, str],
) -> tuple[int, int]:
    listing = client.get("/api/v1/library", headers=headers)
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
        f"/api/v1/object-tokens/objects/{object_id}/tokens",
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

    listing = client.get(f"/api/v1/object-tokens/objects/{object_id}/tokens", headers=headers)
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
        f"/api/v1/object-tokens/objects/{object_id}/tokens",
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

    revoke = client.post(f"/api/v1/object-tokens/tokens/{token['id']}/revoke", headers=headers)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["state"] == "revoked"

    listing = client.get(f"/api/v1/object-tokens/objects/{object_id}/tokens", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["state"] == "revoked"


def test_object_publisher_token_publishes_only_its_bound_object(
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
    admin_headers = {"Authorization": "Bearer fixture-maintainer-token"}
    listing = client.get("/api/v1/library", headers=admin_headers).json()["items"]
    skill = next(item for item in listing if item["kind"] == "skill")
    object_id = int(skill["id"])
    current_release_id = int(skill["current_release"]["release_id"])

    token_response = client.post(
        f"/api/v1/object-tokens/objects/{object_id}/tokens",
        headers=admin_headers,
        json={
            "name": "object-publisher",
            "type": "publisher",
            "scope_type": "object",
            "scope_id": object_id,
        },
    )
    assert token_response.status_code == 201, token_response.text
    raw_token = token_response.json()["raw_token"]
    publisher_headers = {"Authorization": f"Bearer {raw_token}"}
    content = upload_skill_content(
        client, object_id, "test-library-skill", "2.0.0", publisher_headers
    )

    version_response = client.post(
        f"/api/v1/skills/{object_id}/versions",
        headers=publisher_headers,
        json={
            "version": "2.0.0",
            "content_id": content["content_id"],
        },
    )
    assert version_response.status_code == 201, version_response.text

    release_response = client.post(
        f"/api/v1/versions/{version_response.json()['id']}/releases",
        headers=publisher_headers,
    )
    assert release_response.status_code == 201, release_response.text

    create_object = client.post(
        "/api/v1/skills",
        headers=publisher_headers,
        json={"slug": "publisher-escape", "display_name": "Publisher Escape"},
    )
    assert create_object.status_code == 403, create_object.text
    assert "cannot create new objects" in create_object.json()["detail"]

    other_object = client.post(
        "/api/v1/skills",
        headers=admin_headers,
        json={"slug": "other-object", "display_name": "Other Object"},
    )
    assert other_object.status_code == 201, other_object.text
    cross_object_version = client.post(
        f"/api/v1/skills/{other_object.json()['id']}/versions",
        headers=publisher_headers,
        json={
            "version": "1.0.0",
            "content_id": "cnt_crossobjectfixture",
        },
    )
    assert cross_object_version.status_code == 403, cross_object_version.text
    assert "object scope mismatch" in cross_object_version.json()["detail"]

    exposure_response = client.post(
        f"/api/v1/releases/{current_release_id}/exposures",
        headers=publisher_headers,
        json={
            "audience_type": "grant",
            "listing_mode": "direct_only",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert exposure_response.status_code == 403, exposure_response.text
    assert exposure_response.json()["detail"] == "insufficient scope"

    from server.db import get_session_factory
    from server.modules.identity.models import Credential

    with get_session_factory()() as session:
        credential = session.get(Credential, token_response.json()["token"]["id"])
        assert credential is not None
        assert credential.principal_id is not None
        assert credential.grant_id is None
