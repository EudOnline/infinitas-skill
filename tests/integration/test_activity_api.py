from __future__ import annotations

from pathlib import Path

from tests.integration.test_library_api import _prepare_library_client
from tests.integration.test_object_tokens_api import _prepared_object_and_release


def test_activity_api_returns_normalized_token_and_share_records(
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

    token_response = client.post(
        f"/api/objects/{object_id}/tokens",
        headers=headers,
        json={
            "name": "activity-reader",
            "type": "reader",
            "scope_type": "release",
            "scope_id": release_id,
        },
    )
    assert token_response.status_code == 201, token_response.text
    token_id = token_response.json()["token"]["id"]

    share_response = client.post(
        f"/api/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "activity-share", "password": "open"},
    )
    assert share_response.status_code == 201, share_response.text
    share_id = share_response.json()["id"]

    resolved = client.post(f"/api/share-links/{share_id}/resolve", json={"password": "open"})
    assert resolved.status_code == 200, resolved.text

    token_revoke = client.post(f"/api/tokens/{token_id}/revoke", headers=headers)
    assert token_revoke.status_code == 200, token_revoke.text

    response = client.get("/api/activity", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    actions = {item["action"] for item in payload["items"]}
    assert {
        "token.created",
        "token.revoked",
        "share_link.created",
        "share_link.resolved",
    } <= actions
    first = payload["items"][0]
    assert {"id", "actor", "action", "object", "release", "outcome", "timestamp"} <= first.keys()

    token_activity = client.get(f"/api/tokens/{token_id}/activity", headers=headers)
    assert token_activity.status_code == 200, token_activity.text
    assert {item["action"] for item in token_activity.json()["items"]} == {
        "token.created",
        "token.revoked",
    }

    share_activity = client.get(f"/api/share-links/{share_id}/activity", headers=headers)
    assert share_activity.status_code == 200, share_activity.text
    assert {item["action"] for item in share_activity.json()["items"]} >= {
        "share_link.created",
        "share_link.resolved",
    }
