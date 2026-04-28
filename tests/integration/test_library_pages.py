from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.integration.test_library_api import _prepare_library_client
from tests.integration.test_search_install_contract import create_exposure


def _seed_library_access_data(client) -> dict[str, int]:
    from server.db import get_session_factory
    from server.models import AccessGrant, Credential, ReviewCase, utcnow
    from server.modules.access import service as access_service

    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    listing = client.get("/api/library", headers=headers)
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
        public_review_case = session.query(ReviewCase).filter(
            ReviewCase.exposure_id == int(public_exposure["id"])
        ).one()
        public_review_case.state = "approved"
        public_review_case.closed_at = utcnow()

        share_grant = AccessGrant(
            exposure_id=int(grant_exposure["id"]),
            grant_type="link",
            subject_ref="share://demo-skill/release",
            constraints_json=json.dumps(
                {
                    "temporary_password": "moon-door",
                    "expires_at": (now + timedelta(days=7)).isoformat(),
                    "usage_limit": 5,
                    "usage_count": 2,
                },
                ensure_ascii=False,
            ),
            state="active",
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
            hashed_secret=access_service.hash_token("temporary-password"),
            scopes_json=access_service.encode_scopes({"artifact:download"}),
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
        "/library?lang=en",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert response.status_code == 200, response.text
    assert "Library" in response.text
    assert "Demo Skill" in response.text
    assert "Shared Soul" in response.text
    assert "Nano Runner" in response.text


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
    assert '/library?lang=en' in home_html
    assert "Open Library" in home_html

    login = client.get("/login?lang=en")
    assert login.status_code == 200, login.text
    login_html = login.text
    assert "/library" in login_html
    assert "/skills" not in login_html
    assert "Admin distribution" in login_html


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

    listing = client.get("/api/library", headers=headers)
    assert listing.status_code == 200, listing.text
    object_payload = next(
        item for item in listing.json()["items"] if item["kind"] == "agent_preset"
    )
    object_id = object_payload["id"]
    release_id = object_payload["current_release"]["release_id"]

    detail = client.get(f"/library/{object_id}?lang=en", headers=headers)
    assert detail.status_code == 200, detail.text
    assert "Shared Soul" in detail.text
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
    assert "Distribution summary" in html
    assert "Visibility channels" in html
    assert "Agent tokens" in html
    assert "Share links" in html
    assert "Manage visibility" in html
    assert 'id="create-exposure-form"' in html
    assert 'data-action="activate-exposure"' in html
    assert 'data-action="revoke-exposure"' in html
    assert 'data-action="toggle-patch-form"' in html
    assert "Issue agent token" in html
    assert 'id="issue-token-form"' in html
    assert "Create share link" in html
    assert 'id="create-share-form"' in html


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

    assert "Demo Skill" in html
    assert "#1" in html or "#2" in html
    assert "reader" in html
    assert "publisher" in html
    assert "Yes" in html
    assert "2 / 5" in html


def test_access_center_and_shares_pages_render_real_inventory(
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

    access_response = client.get("/access?lang=en", headers=headers)
    assert access_response.status_code == 200, access_response.text
    access_html = access_response.text
    assert "Demo Skill" in access_html
    assert "reader" in access_html
    assert "publisher" in access_html
    assert "Token activity" in access_html

    shares_response = client.get("/shares?lang=en", headers=headers)
    assert shares_response.status_code == 200, shares_response.text
    shares_html = shares_response.text
    assert "Demo Skill" in shares_html
    assert "1.0.0" in shares_html
    assert "Yes" in shares_html
    assert "2 / 5" in shares_html


def test_access_center_and_shares_pages_offer_revoke_actions(
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

    access_response = client.get("/access?lang=en", headers=headers)
    assert access_response.status_code == 200, access_response.text
    assert 'data-action="revoke-token"' in access_response.text

    shares_response = client.get("/shares?lang=en", headers=headers)
    assert shares_response.status_code == 200, shares_response.text
    assert 'data-action="revoke-share-link"' in shares_response.text


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

    revoke_token = client.post(
        f"/api/library/tokens/{seeded['reader_credential_id']}/revoke",
        headers=headers,
    )
    assert revoke_token.status_code == 200, revoke_token.text

    revoke_share = client.post(
        f"/api/library/share-links/{seeded['share_grant_id']}/revoke",
        headers=headers,
    )
    assert revoke_share.status_code == 200, revoke_share.text

    access_response = client.get("/access?lang=en", headers=headers)
    assert access_response.status_code == 200, access_response.text
    assert "revoked" in access_response.text

    shares_response = client.get("/shares?lang=en", headers=headers)
    assert shares_response.status_code == 200, shares_response.text
    assert "revoked" in shares_response.text


def test_access_and_shares_pages_show_labels_for_items_created_from_release_page(
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
        f"/api/library/releases/{seeded['release_id']}/tokens",
        headers=headers,
        json={"token_type": "publisher", "label": "Deploy Bot"},
    )
    assert token_response.status_code == 201, token_response.text

    share_response = client.post(
        f"/api/library/releases/{seeded['release_id']}/share-links",
        headers=headers,
        json={
            "label": "QA Share",
            "temporary_password": "moon-door",
            "expires_in_days": 7,
            "usage_limit": 5,
        },
    )
    assert share_response.status_code == 201, share_response.text

    access_response = client.get("/access?lang=en", headers=headers)
    assert access_response.status_code == 200, access_response.text
    access_html = access_response.text
    assert "Deploy Bot" in access_html
    assert "1.0.0" in access_html

    shares_response = client.get("/shares?lang=en", headers=headers)
    assert shares_response.status_code == 200, shares_response.text
    shares_html = shares_response.text
    assert "QA Share" in shares_html
    assert "1.0.0" in shares_html


def test_activity_page_derives_visibility_token_and_share_timeline(
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

    response = client.get("/activity?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    html = response.text

    assert "Demo Skill" in html
    assert "visibility" in html
    assert "token" in html
    assert "share" in html


def test_activity_page_includes_token_revocation_events(
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

    revoke_token = client.post(
        f"/api/library/tokens/{seeded['reader_credential_id']}/revoke",
        headers=headers,
    )
    assert revoke_token.status_code == 200, revoke_token.text

    response = client.get("/activity?lang=en", headers=headers)
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
    assert "Access Center" in html
    assert "Share Links" in html
    assert "Public releases" in html
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
