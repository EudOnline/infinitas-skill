from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.modules.identity.auth import AUTH_COOKIE_NAME, create_auth_session_cookie
from server.modules.identity.models import Credential
from server.modules.identity.service import create_fresh_session_credential
from tests.integration.conftest import _prepare_library_client


def _session_headers(client: TestClient) -> dict[str, str]:
    from server.db import get_session_factory

    with get_session_factory()() as db:
        personal = db.query(Credential).filter(Credential.type == "personal_token").first()
        assert personal is not None and personal.principal_id is not None
        session = create_fresh_session_credential(db, principal_id=personal.principal_id)
        db.commit()
        session_id = session.id
    csrf = "namespace-token-csrf"
    client.cookies.set(AUTH_COOKIE_NAME, create_auth_session_cookie(session_id))
    client.cookies.set("csrf_token", csrf)
    return {"X-CSRF-Token": csrf}


def test_namespace_publisher_creates_new_skills_and_reader_is_read_only(
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
    session_headers = _session_headers(client)
    publisher_response = client.post(
        "/api/v1/namespace-tokens",
        headers=session_headers,
        json={
            "name": "namespace-publisher",
            "type": "publisher",
            "issued_for": "agent-e2e",
            "max_daily_publishes": 20,
        },
    )
    assert publisher_response.status_code == 201, publisher_response.text
    publisher = publisher_response.json()
    assert publisher["token"]["scope_type"] == "namespace"
    assert publisher["token"]["scopes"] == [
        "artifact:download",
        "exposure:write",
        "registry:publish",
        "registry:read",
        "release:write",
        "skill:create",
    ]
    publisher_headers = {"Authorization": f"Bearer {publisher['raw_token']}"}
    created = client.post(
        "/api/v1/skills",
        headers=publisher_headers,
        json={"slug": "namespace-created", "display_name": "Namespace Created"},
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/v1/skills", headers=publisher_headers)
    assert listed.status_code == 200, listed.text
    assert {item["slug"] for item in listed.json()} >= {
        "namespace-created",
        "test-library-skill",
    }
    delegated = client.post(
        f"/api/v1/object-tokens/objects/{created.json()['id']}/tokens",
        headers=publisher_headers,
        json={
            "name": "self-delegated",
            "type": "publisher",
            "scope_type": "object",
            "scope_id": created.json()["id"],
        },
    )
    assert delegated.status_code == 403, delegated.text
    assert delegated.json()["detail"] == "admin credential required"
    policy_update = client.patch(
        f"/api/v1/credentials/{publisher['token']['id']}/policy",
        headers=publisher_headers,
        json={"max_daily_publishes": 100000},
    )
    assert policy_update.status_code == 403, policy_update.text
    assert policy_update.json()["detail"] == "admin credential required"

    reader_response = client.post(
        "/api/v1/namespace-tokens",
        headers=session_headers,
        json={"name": "namespace-reader", "type": "reader"},
    )
    assert reader_response.status_code == 201, reader_response.text
    reader = reader_response.json()
    assert reader["token"]["scopes"] == ["artifact:download", "registry:read"]
    reader_headers = {"Authorization": f"Bearer {reader['raw_token']}"}
    catalog = client.get("/api/v1/registry/ai-index.json", headers=reader_headers)
    assert catalog.status_code == 200, catalog.text
    trust = client.get("/api/v1/registry/trust-bootstrap.json", headers=reader_headers)
    assert trust.status_code == 200, trust.text
    assert trust.json()["allowed_signers"].strip()
    denied = client.post(
        "/api/v1/skills",
        headers=reader_headers,
        json={"slug": "reader-write", "display_name": "Reader Write"},
    )
    assert denied.status_code == 403, denied.text


def test_namespace_tokens_require_browser_session_and_can_be_revoked(
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
    bearer = client.post(
        "/api/v1/namespace-tokens",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
        json={"name": "forbidden", "type": "publisher"},
    )
    assert bearer.status_code == 403, bearer.text
    assert bearer.json()["detail"] == "browser session required"

    session_headers = _session_headers(client)
    created = client.post(
        "/api/v1/namespace-tokens",
        headers=session_headers,
        json={"name": "revoke-me", "type": "publisher"},
    )
    assert created.status_code == 201, created.text
    token_id = created.json()["token"]["id"]
    listing = client.get("/api/v1/namespace-tokens")
    assert listing.status_code == 200, listing.text
    assert token_id in {item["id"] for item in listing.json()["items"]}
    revoked = client.post(
        f"/api/v1/namespace-tokens/{token_id}/revoke",
        headers=session_headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["state"] == "revoked"
