from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_agent_code_import import _create_external_agent_repo
from tests.integration.test_multi_object_registry_surfaces import (
    _activate_private_exposure,
    _create_agent_code_release,
    _create_agent_preset_release,
    _create_skill_release,
)
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _prepare_library_client(
    monkeypatch,
    *,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> TestClient:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)

    upstream_repo = tmp_path / "external-agent-code"
    commit = _create_external_agent_repo(upstream_repo)

    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_ids = [
        _create_skill_release(client),
        _create_agent_preset_release(client),
        _create_agent_code_release(client, upstream_repo=upstream_repo, commit=commit),
    ]
    processed = run_worker_loop(limit=3)
    assert processed == 3
    for release_id in release_ids:
        _activate_private_exposure(client, release_id)
    return client


def test_library_list_returns_multi_object_cards(
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

    response = client.get(
        "/api/library",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert {item["kind"] for item in payload["items"]} >= {"skill", "agent_preset", "agent_code"}

    shared_fields = {
        "id",
        "kind",
        "slug",
        "display_name",
        "summary",
        "current_release",
        "current_visibility",
        "token_count",
        "share_link_count",
    }
    first = payload["items"][0]
    assert shared_fields.issubset(first.keys())


def test_library_detail_returns_type_specific_payloads(
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

    listing = client.get("/api/library", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]

    by_kind = {item["kind"]: item for item in items}

    skill_detail = client.get(f"/api/library/{by_kind['skill']['id']}", headers=headers)
    assert skill_detail.status_code == 200, skill_detail.text
    assert skill_detail.json()["details"]["kind"] == "skill"

    preset_detail = client.get(f"/api/library/{by_kind['agent_preset']['id']}", headers=headers)
    assert preset_detail.status_code == 200, preset_detail.text
    assert preset_detail.json()["details"]["runtime_family"] == "openclaw"
    assert preset_detail.json()["details"]["supported_memory_modes"] == ["local", "shared"]

    code_detail = client.get(f"/api/library/{by_kind['agent_code']['id']}", headers=headers)
    assert code_detail.status_code == 200, code_detail.text
    assert code_detail.json()["details"]["language"] == "python"
    assert code_detail.json()["details"]["entrypoint"] == "main.py"


def test_library_release_listing_returns_release_rows(
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

    listing = client.get("/api/library", headers=headers)
    assert listing.status_code == 200, listing.text
    skill_id = next(item["id"] for item in listing.json()["items"] if item["kind"] == "skill")

    releases = client.get(f"/api/library/{skill_id}/releases", headers=headers)
    assert releases.status_code == 200, releases.text
    payload = releases.json()
    assert payload["items"], payload
    assert payload["items"][0]["state"] == "ready"
    assert payload["items"][0]["visibility"]["audience_type"] == "private"


def test_library_release_actions_issue_token_and_share_link(
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

    listing = client.get("/api/library", headers=headers)
    assert listing.status_code == 200, listing.text
    skill_object = next(item for item in listing.json()["items"] if item["kind"] == "skill")
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

    token_response = client.post(
        f"/api/library/releases/{release_id}/tokens",
        headers=headers,
        json={"token_type": "publisher", "label": "Deploy Bot"},
    )
    assert token_response.status_code == 201, token_response.text
    token_payload = token_response.json()
    assert token_payload["token_type"] == "publisher"
    assert token_payload["token"].startswith("grant_")
    assert "release:write" in token_payload["scopes"]

    share_response = client.post(
        f"/api/library/releases/{release_id}/share-links",
        headers=headers,
        json={
            "label": "QA share",
            "temporary_password": "moon-door",
            "expires_in_days": 7,
            "usage_limit": 5,
        },
    )
    assert share_response.status_code == 201, share_response.text
    share_payload = share_response.json()
    assert share_payload["temporary_password"] == "moon-door"
    assert share_payload["usage_limit"] == 5
    assert "/api/v1/install/grant/" in share_payload["install_path"]

    detail = client.get(f"/api/library/{skill_object['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["object"]["token_count"] >= 1
    assert detail.json()["object"]["share_link_count"] >= 1


def test_library_admin_api_can_revoke_token_and_share_link(
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
    from tests.integration.test_library_pages import _seed_library_access_data

    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    token_response = client.post(
        f"/api/library/tokens/{seeded['reader_credential_id']}/revoke",
        headers=headers,
    )
    assert token_response.status_code == 200, token_response.text
    assert token_response.json()["state"] == "revoked"

    share_response = client.post(
        f"/api/library/share-links/{seeded['share_grant_id']}/revoke",
        headers=headers,
    )
    assert share_response.status_code == 200, share_response.text
    assert share_response.json()["state"] == "revoked"
