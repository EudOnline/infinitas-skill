from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import event as sqlalchemy_event

from tests.integration.conftest import _prepare_library_client
from tests.integration.test_search_install_contract import create_exposure


def _seed_library_access_data(client) -> dict[str, int]:
    from server.db import get_session_factory
    from server.model_base import utcnow
    from server.modules.access import service as access_service
    from server.modules.access.models import AccessGrant
    from server.modules.identity import service as identity_service
    from server.modules.identity.models import Credential
    from server.modules.review.models import ReviewCase

    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    listing = client.get("/api/v1/library", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]

    skill_object = next(item for item in items if item["kind"] == "skill")
    skill_object_id = int(skill_object["id"])
    skill_release_id = int(skill_object["current_release"]["release_id"])

    grant_exposure = create_exposure(
        client,
        headers,
        release_id=skill_release_id,
        audience_type="grant",
        listing_mode="direct_only",
        requested_review_mode="none",
    )
    public_exposure = create_exposure(
        client,
        headers,
        release_id=skill_release_id,
        audience_type="public",
        listing_mode="listed",
        requested_review_mode="none",
    )

    now = datetime.now(timezone.utc)
    session_factory = get_session_factory()
    with session_factory() as session:
        public_review_case = (
            session.query(ReviewCase)
            .filter(ReviewCase.exposure_id == int(public_exposure["id"]))
            .one()
        )
        public_review_case.state = "approved"
        public_review_case.closed_at = utcnow()
        public_review_case_id = int(public_review_case.id)

        share_grant = AccessGrant(
            exposure_id=int(grant_exposure["id"]),
            grant_type="link",
            subject_ref="share://demo-skill/release",
            constraints_json=json.dumps({"temporary_password": "moon-door"}, ensure_ascii=False),
            state="active",
            expires_at=now + timedelta(days=7),
            usage_limit=5,
            usage_count=2,
        )
        reader_grant = AccessGrant(
            exposure_id=int(grant_exposure["id"]),
            grant_type="token",
            subject_ref="agent://demo-skill/reader",
            constraints_json=json.dumps({"usage_count": 3}, ensure_ascii=False),
            state="active",
        )
        publisher_grant = AccessGrant(
            exposure_id=int(grant_exposure["id"]),
            grant_type="token",
            subject_ref="agent://demo-skill/publisher",
            constraints_json=json.dumps(
                {
                    "usage_count": 1,
                },
                ensure_ascii=False,
            ),
            state="active",
        )
        session.add_all([share_grant, reader_grant, publisher_grant])
        session.flush()

        _reader_token, reader_credential = access_service.create_grant_token(
            session,
            grant=reader_grant,
            scopes={"artifact:download"},
        )
        _publisher_token, publisher_credential = access_service.create_grant_token(
            session,
            grant=publisher_grant,
            scopes={"release:write"},
        )
        reader_credential.last_used_at = now - timedelta(hours=2)
        publisher_credential.last_used_at = now - timedelta(minutes=30)

        share_password_credential = Credential(
            principal_id=None,
            grant_id=share_grant.id,
            type="share_password",
            hashed_secret=identity_service.hash_token("temporary-password"),
            scopes_json=identity_service.encode_scopes({"artifact:download"}),
            resource_selector_json=json.dumps({"release_scope": "grant-bound"}, ensure_ascii=False),
            expires_at=now + timedelta(days=7),
            created_at=now - timedelta(days=1),
        )
        session.add(share_password_credential)
        session.commit()

    return {
        "object_id": skill_object_id,
        "release_id": skill_release_id,
        "grant_exposure_id": int(grant_exposure["id"]),
        "public_exposure_id": int(public_exposure["id"]),
        "public_review_case_id": public_review_case_id,
        "share_grant_id": int(share_grant.id),
        "reader_credential_id": int(reader_credential.id),
        "publisher_credential_id": int(publisher_credential.id),
    }


def test_library_page_loads_with_multi_object_cards(
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
        "/manage?lang=en",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert response.status_code == 200, response.text
    assert "Test Library Skill" in response.text


def test_home_and_login_pages_promote_library_as_admin_entry(
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

    home = client.get("/?lang=en")
    assert home.status_code == 200, home.text
    home_html = home.text
    assert "/manage?lang=en" in home_html
    assert "Open Library" in home_html

    login = client.get("/login?lang=en")
    assert login.status_code == 200, login.text
    login_html = login.text
    assert "/manage" in login_html
    assert "/skills" not in login_html
    assert "Admin distribution" in login_html


def test_removed_maintainer_console_aliases_return_not_found(
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

    skills = client.get("/skills?lang=en", headers=headers, follow_redirects=False)
    assert skills.status_code == 404

    skill_detail = client.get("/skills/1?lang=en", headers=headers, follow_redirects=False)
    assert skill_detail.status_code == 404

    draft_detail = client.get("/drafts/1?lang=en", headers=headers, follow_redirects=False)
    assert draft_detail.status_code == 404


def test_library_object_and_release_pages_render(
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

    listing = client.get("/api/v1/library", headers=headers)
    assert listing.status_code == 200, listing.text
    object_payload = next(item for item in listing.json()["items"] if item["kind"] == "skill")
    object_id = object_payload["id"]
    release_id = object_payload["current_release"]["release_id"]

    detail = client.get(f"/library/{object_id}?lang=en", headers=headers)
    assert detail.status_code == 200, detail.text
    assert "Test Library Skill" in detail.text
    assert "Releases" in detail.text

    release_detail = client.get(
        f"/library/{object_id}/releases/{release_id}?lang=en",
        headers=headers,
    )
    assert release_detail.status_code == 200, release_detail.text
    assert "Release" in release_detail.text
    assert "private" in release_detail.text


def test_library_release_page_shows_real_artifacts_and_distribution_summary(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    release_detail = client.get(
        f"/library/{seeded['object_id']}/releases/{seeded['release_id']}?lang=en",
        headers=headers,
    )
    assert release_detail.status_code == 200, release_detail.text
    html = release_detail.text

    for label in ["Manifest", "Bundle", "Provenance", "Signature"]:
        assert label in html
    assert "Channels" in html
    assert "Agent tokens" in html
    assert "Links" in html
    assert "Visibility" in html
    assert 'id="create-exposure-form"' in html
    assert 'data-action="activate-exposure"' in html
    assert 'data-action="revoke-exposure"' in html
    assert 'data-action="toggle-patch-form"' in html
    assert 'data-action="review-detail"' in html
    assert "Issue token" in html
    assert 'id="issue-token-form"' in html
    assert "Create link" in html
    assert 'id="create-share-form"' in html


def test_library_release_page_exposes_review_actions_without_allowing_self_review(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    from server.db import get_session_factory
    from server.modules.exposure.models import Exposure
    from server.modules.review.models import ReviewCase

    client = _prepare_library_client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    session_factory = get_session_factory()

    with session_factory() as session:
        review_case = session.get(ReviewCase, seeded["public_review_case_id"])
        exposure = session.get(Exposure, seeded["public_exposure_id"])
        assert review_case is not None
        assert exposure is not None
        review_case.state = "open"
        review_case.closed_at = None
        exposure.state = "review_open"
        session.commit()

    detail_url = f"/library/{seeded['object_id']}/releases/{seeded['release_id']}?lang=en"
    self_review_page = client.get(detail_url, headers=headers)
    assert self_review_page.status_code == 200, self_review_page.text
    assert "A different maintainer must review" in self_review_page.text
    assert 'data-action="review-approve"' not in self_review_page.text

    with session_factory() as session:
        exposure = session.get(Exposure, seeded["public_exposure_id"])
        assert exposure is not None
        exposure.requested_by_principal_id = None
        session.commit()

    review_page = client.get(detail_url, headers=headers)
    assert review_page.status_code == 200, review_page.text
    assert 'data-action="toggle-review-form"' in review_page.text
    assert 'data-action="review-approve"' in review_page.text
    assert 'data-action="review-reject"' in review_page.text
    assert 'data-action="review-comment"' in review_page.text

    approved = client.post(
        f"/api/v1/review-cases/{seeded['public_review_case_id']}/decisions",
        headers=headers,
        json={"decision": "approve", "note": "approved from web workflow"},
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["state"] == "approved"


def test_release_admin_requires_confirmation_for_irreversible_actions() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "server"
        / "static"
        / "js"
        / "modules"
        / "lifecycle.js"
    ).read_text(encoding="utf-8")

    for key in (
        "confirm_revoke_exposure",
        "confirm_review_approve",
        "confirm_review_reject",
    ):
        assert key in source


def test_library_object_detail_shows_real_token_and_share_rows(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    detail = client.get(f"/library/{seeded['object_id']}?lang=en", headers=headers)
    assert detail.status_code == 200, detail.text
    html = detail.text

    assert "Test Library Skill" in html
    assert "reader" in html
    assert "publisher" in html
    assert "2/5" in html


def test_manage_page_renders_token_and_share_inventory(
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
    _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    # Removed aliases stay absent; the consolidated page is the only entry point.
    access_redirect = client.get("/access?lang=en", headers=headers, follow_redirects=False)
    assert access_redirect.status_code == 404

    manage_response = client.get("/manage?lang=en", headers=headers)
    assert manage_response.status_code == 200, manage_response.text
    manage_html = manage_response.text
    assert "Test Library Skill" in manage_html
    assert "reader" in manage_html
    assert "publisher" in manage_html
    assert "2/5" in manage_html


def test_manage_page_shows_grant_share_usage_aliases(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    from server.db import get_session_factory
    from server.modules.access.models import AccessGrant

    session_factory = get_session_factory()
    with session_factory() as session:
        share_grant = session.get(AccessGrant, seeded["share_grant_id"])
        assert share_grant is not None
        share_grant.constraints_json = json.dumps(
            {"name": "Grant-backed exhausted share"},
            ensure_ascii=False,
        )
        share_grant.usage_count = 1
        share_grant.usage_limit = 1
        session.add(share_grant)
        session.commit()

    manage_response = client.get("/manage?lang=en", headers=headers)
    assert manage_response.status_code == 200, manage_response.text
    manage_html = manage_response.text

    assert "Grant-backed exhausted share" in manage_html
    assert "1/1" in manage_html
    assert "exhausted" in manage_html


def test_manage_page_offers_revoke_actions(
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
    _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    manage_response = client.get("/manage?lang=en", headers=headers)
    assert manage_response.status_code == 200, manage_response.text
    manage_html = manage_response.text
    assert 'data-action="revoke-token"' in manage_html
    assert 'data-action="revoke-share-link"' in manage_html


def test_revoked_token_and_share_remain_visible_in_inventory(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    token_response = client.post(
        f"/api/v1/object-tokens/objects/{seeded['object_id']}/tokens",
        headers=headers,
        json={
            "name": "revoke-test-token",
            "type": "reader",
            "scope_type": "release",
            "scope_id": seeded["release_id"],
        },
    )
    assert token_response.status_code == 201, token_response.text
    token_id = token_response.json()["token"]["id"]

    revoke_token = client.post(
        f"/api/v1/object-tokens/tokens/{token_id}/revoke",
        headers=headers,
    )
    assert revoke_token.status_code == 200, revoke_token.text

    revoke_share = client.post(
        f"/api/v1/share-links/{seeded['share_grant_id']}/revoke",
        headers=headers,
    )
    assert revoke_share.status_code == 200, revoke_share.text

    manage_response = client.get("/manage?lang=en", headers=headers)
    assert manage_response.status_code == 200, manage_response.text
    assert "revoked" in manage_response.text


def test_manage_page_shows_labels_for_items_created_from_release_page(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    token_response = client.post(
        f"/api/v1/object-tokens/objects/{seeded['object_id']}/tokens",
        headers=headers,
        json={
            "name": "Deploy Bot",
            "type": "publisher",
            "scope_type": "release",
            "scope_id": seeded["release_id"],
        },
    )
    assert token_response.status_code == 201, token_response.text

    share_response = client.post(
        f"/api/v1/share-links/releases/{seeded['release_id']}/share-links",
        headers=headers,
        json={
            "name": "QA Share",
            "password": "moon-door",
            "expires_in_days": 7,
            "max_uses": 5,
        },
    )
    assert share_response.status_code == 201, share_response.text

    manage_response = client.get("/manage?lang=en", headers=headers)
    assert manage_response.status_code == 200, manage_response.text
    manage_html = manage_response.text
    assert "Deploy Bot" in manage_html
    assert "QA Share" in manage_html
    assert "1.0.0" in manage_html


def test_manage_page_renders_normalized_audit_events(
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
    from server.db import get_session_factory
    from server.modules.audit import service as audit_service

    session_factory = get_session_factory()
    with session_factory() as session:
        audit_service.append_audit_event(
            session,
            aggregate_type="share_link",
            aggregate_id="audit-share-1",
            event_type="share_link.created",
            actor_ref="principal:audit-fixture",
            payload={
                "object_id": 999999,
                "release_id": 888888,
                "object_name": "Audit Only Object",
                "title": "Audit-only share created",
                "description": "Rendered from audit payload, not library projection.",
            },
        )
        session.commit()

    response = client.get("/manage?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    html = response.text

    assert "Audit Only Object" in html
    assert "Audit-only share created" in html
    assert "audit-fixture" in html
    assert "share" in html


def test_ui_activity_normalization_uses_bounded_queries(
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
    listing = client.get("/api/v1/library", headers=headers).json()["items"]
    skill = next(item for item in listing if item["kind"] == "skill")
    object_id = int(skill["id"])
    release_id = int(skill["current_release"]["release_id"])

    from server.db import get_engine, get_session_factory
    from server.modules.audit import service as audit_service
    from server.ui.activity import list_activity_rows

    session_factory = get_session_factory()
    with session_factory() as session:
        for index in range(20):
            audit_service.append_audit_event(
                session,
                aggregate_type="share_link",
                aggregate_id=f"query-count-{index}",
                event_type="share_link.created",
                actor_ref="principal:query-count",
                payload={"object_id": object_id, "release_id": release_id},
            )
        session.commit()

        statements = 0

        def count_statement(*_args) -> None:
            nonlocal statements
            statements += 1

        engine = get_engine()
        sqlalchemy_event.listen(engine, "before_cursor_execute", count_statement)
        try:
            rows = list_activity_rows(session, limit=100)
        finally:
            sqlalchemy_event.remove(engine, "before_cursor_execute", count_statement)

    assert rows
    assert statements == 3


def test_manage_page_includes_token_revocation_events(
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
    seeded = _seed_library_access_data(client)
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    token_response = client.post(
        f"/api/v1/object-tokens/objects/{seeded['object_id']}/tokens",
        headers=headers,
        json={
            "name": "event-test-token",
            "type": "reader",
            "scope_type": "release",
            "scope_id": seeded["release_id"],
        },
    )
    assert token_response.status_code == 201, token_response.text
    token_id = token_response.json()["token"]["id"]

    revoke_token = client.post(
        f"/api/v1/object-tokens/tokens/{token_id}/revoke",
        headers=headers,
    )
    assert revoke_token.status_code == 200, revoke_token.text

    response = client.get("/manage?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    html = response.text

    assert "revoked" in html
    assert "reader token revoked" in html


def test_settings_page_centers_admin_token_and_distribution_flow(
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

    response = client.get("/settings?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    html = response.text

    assert "INFINITAS_REGISTRY_API_TOKEN" in html
    assert "Access" in html
    assert "Shares" in html
    assert "OpenClaw" not in html


def test_settings_page_keeps_focus_on_primary_admin_flow(
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

    response = client.get("/settings?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    html = response.text

    assert "Compatibility tools" not in html
    assert "/skills?lang=en" not in html
    assert "/review-cases?lang=en" not in html
    assert "Authoring console" not in html
