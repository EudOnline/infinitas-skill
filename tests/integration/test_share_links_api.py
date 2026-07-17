from __future__ import annotations

import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.integration.conftest import _prepare_library_client
from tests.integration.test_object_tokens_api import _prepared_object_and_release


def test_share_links_module_is_removed() -> None:
    """The standalone shares module must be consolidated into the access package."""
    assert "server.modules.shares" not in sys.modules
    spec = importlib.util.find_spec("server.modules.shares")
    assert spec is None


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
        f"/api/v1/share-links/releases/{release_id}/share-links",
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
    assert share["id"] == share["grant_id"]
    assert share["name"] == "temp-share"
    assert share["has_password"] is True
    assert share["max_uses"] == 3
    assert share["used_count"] == 0
    assert share["state"] == "active"
    assert "password" not in share
    assert "credential_id" in share
    assert share["resolve_url"].endswith(f"/api/v1/share-links/{share['id']}/resolve")
    assert share["resolve_secret"] is None

    listing = client.get(f"/api/v1/share-links/releases/{release_id}/share-links", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["has_password"] is True
    assert listing.json()["items"][0]["id"] == share["grant_id"]

    wrong_password = client.post(
        f"/api/v1/share-links/{share['id']}/resolve",
        json={"password": "wrong"},
    )
    assert wrong_password.status_code == 403, wrong_password.text

    resolved = client.post(
        f"/api/v1/share-links/{share['id']}/resolve",
        json={"password": "123456"},
    )
    assert resolved.status_code == 200, resolved.text
    resolved_payload = resolved.json()
    assert resolved_payload["release_id"] == release_id
    assert resolved_payload["used_count"] == 1
    assert "/api/v1/install/grant/" in resolved_payload["install_path"]
    assert resolved_payload["access_token"].startswith("grant_")

    install = client.get(
        resolved_payload["install_path"],
        headers={"Authorization": f"Bearer {resolved_payload['access_token']}"},
    )
    assert install.status_code == 200, install.text
    assert install.json()["release_id"] == release_id

    from server.db import get_session_factory
    from server.modules.access.models import AccessGrant
    from server.modules.audit.models import AuditEvent
    from server.modules.identity.models import Credential

    session_factory = get_session_factory()
    with session_factory() as session:
        grant = session.get(AccessGrant, share["grant_id"])
        assert grant is not None
        assert grant.grant_type == "link"
        credentials = session.query(Credential).filter(Credential.grant_id == grant.id).all()
        assert {credential.type for credential in credentials} == {
            "share_password",
            "grant_token",
        }
        events = (
            session.query(AuditEvent)
            .filter(AuditEvent.aggregate_type == "share_link")
            .filter(AuditEvent.aggregate_id == str(grant.id))
            .order_by(AuditEvent.id)
            .all()
        )
        assert [event.event_type for event in events] == [
            "share_link.created",
            "share_link.resolved",
        ]


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
        f"/api/v1/share-links/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "short-link", "max_uses": 1},
    )
    assert created.status_code == 201, created.text
    share_id = created.json()["id"]

    revoke = client.post(f"/api/v1/share-links/{share_id}/revoke", headers=headers)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["state"] == "revoked"

    resolved = client.post(f"/api/v1/share-links/{share_id}/resolve", json={})
    assert resolved.status_code == 410, resolved.text

    from server.db import get_session_factory
    from server.modules.access.models import AccessGrant
    from server.modules.audit.models import AuditEvent
    from server.modules.identity.models import Credential

    session_factory = get_session_factory()
    with session_factory() as session:
        grant = session.get(AccessGrant, share_id)
        assert grant is not None
        assert grant.state == "revoked"
        credentials = session.query(Credential).filter(Credential.grant_id == share_id).all()
        assert credentials
        assert all(credential.revoked_at is not None for credential in credentials)
        events = (
            session.query(AuditEvent)
            .filter(AuditEvent.aggregate_type == "share_link")
            .filter(AuditEvent.aggregate_id == str(share_id))
            .order_by(AuditEvent.id)
            .all()
        )
        assert [event.event_type for event in events] == [
            "share_link.created",
            "share_link.revoked",
        ]


def test_passwordless_share_link_resolves_without_legacy_share_row(
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
        f"/api/v1/share-links/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "open-share", "max_uses": 2},
    )
    assert response.status_code == 201, response.text
    share = response.json()
    assert share["has_password"] is False
    assert share["credential_id"] is not None
    assert share["max_uses"] == 2
    assert share["used_count"] == 0
    assert share["resolve_secret"]

    missing_secret = client.post(f"/api/v1/share-links/{share['id']}/resolve", json={})
    assert missing_secret.status_code == 403, missing_secret.text

    resolved = client.post(
        f"/api/v1/share-links/{share['id']}/resolve",
        json={"secret": share["resolve_secret"]},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["used_count"] == 1
    assert resolved.json()["access_token"].startswith("grant_")

    from server.db import get_session_factory
    from server.modules.access.models import AccessGrant
    from server.modules.audit.models import AuditEvent
    from server.modules.identity.models import Credential

    session_factory = get_session_factory()
    with session_factory() as session:
        grant = session.get(AccessGrant, share["grant_id"])
        assert grant is not None
        credentials = session.query(Credential).filter(Credential.grant_id == grant.id).all()
        assert {credential.type for credential in credentials} == {
            "share_capability",
            "grant_token",
        }
        events = (
            session.query(AuditEvent)
            .filter(AuditEvent.aggregate_type == "share_link")
            .filter(AuditEvent.aggregate_id == str(grant.id))
            .order_by(AuditEvent.id)
            .all()
        )
        assert [event.event_type for event in events] == [
            "share_link.created",
            "share_link.resolved",
        ]


def test_share_link_usage_limit_is_atomic_under_concurrency(
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
        f"/api/v1/share-links/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "single-use", "max_uses": 1},
    )
    assert created.status_code == 201, created.text
    share = created.json()
    share_id = share["id"]
    resolve_secret = share["resolve_secret"]

    def resolve() -> int:
        return client.post(
            f"/api/v1/share-links/{share_id}/resolve",
            json={"secret": resolve_secret},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _index: resolve(), range(2)))

    assert statuses == [200, 410]
