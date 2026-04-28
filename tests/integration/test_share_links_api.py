from __future__ import annotations

from pathlib import Path

from tests.integration.test_library_api import _prepare_library_client
from tests.integration.test_object_tokens_api import _prepared_object_and_release


def test_create_passworded_share_link_and_resolve(
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
    _object_id, release_id = _prepared_object_and_release(client, headers=headers)

    response = client.post(
        f"/api/releases/{release_id}/share-links",
        headers=headers,
        json={
            "name": "temp-share",
            "password": "123456",
            "expires_in_days": 7,
            "max_uses": 3,
        },
    )
    assert response.status_code == 201, response.text
    share = response.json()
    assert share["name"] == "temp-share"
    assert share["has_password"] is True
    assert share["max_uses"] == 3
    assert share["used_count"] == 0
    assert share["state"] == "active"
    assert "password" not in share

    listing = client.get(f"/api/releases/{release_id}/share-links", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["has_password"] is True

    wrong_password = client.post(
        f"/api/share-links/{share['id']}/resolve",
        json={"password": "wrong"},
    )
    assert wrong_password.status_code == 403, wrong_password.text

    resolved = client.post(
        f"/api/share-links/{share['id']}/resolve",
        json={"password": "123456"},
    )
    assert resolved.status_code == 200, resolved.text
    resolved_payload = resolved.json()
    assert resolved_payload["release_id"] == release_id
    assert resolved_payload["used_count"] == 1
    assert "/api/v1/install/grant/" in resolved_payload["install_path"]


def test_revoke_share_link_blocks_resolution(
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
    _object_id, release_id = _prepared_object_and_release(client, headers=headers)

    created = client.post(
        f"/api/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "short-link", "max_uses": 1},
    )
    assert created.status_code == 201, created.text
    share_id = created.json()["id"]

    revoke = client.post(f"/api/share-links/{share_id}/revoke", headers=headers)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["state"] == "revoked"

    resolved = client.post(f"/api/share-links/{share_id}/resolve", json={})
    assert resolved.status_code == 410, resolved.text
