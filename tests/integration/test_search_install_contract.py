from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select


def configure_env(tmpdir: Path) -> Path:
    artifact_root = tmpdir / "artifacts"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(artifact_root)
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "fixture-maintainer",
                "display_name": "Fixture Maintainer",
                "role": "maintainer",
                "token": "fixture-maintainer-token",
            }
        ]
    )
    return artifact_root


def create_ready_release(client, headers: dict[str, str], *, slug: str, display_name: str) -> int:
    from server.worker import run_worker_loop

    create_skill_response = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": slug,
            "display_name": display_name,
            "summary": f"{display_name} summary",
        },
    )
    assert create_skill_response.status_code == 201, create_skill_response.text
    skill_id = int(create_skill_response.json()["id"])

    create_draft_response = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": f"git+https://example.com/{slug}.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert create_draft_response.status_code == 201, create_draft_response.text
    draft_id = int(create_draft_response.json()["id"])

    seal_response = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal_response.status_code == 201, seal_response.text
    version_id = int((seal_response.json().get("skill_version") or {})["id"])

    create_release_response = client.post(
        f"/api/v1/versions/{version_id}/releases",
        headers=headers,
    )
    assert create_release_response.status_code == 201, create_release_response.text
    release_id = int(create_release_response.json()["id"])

    processed = run_worker_loop(limit=1)
    assert processed == 1, f"expected worker to process 1 release job, got {processed}"
    return release_id


def create_exposure(
    client,
    headers: dict[str, str],
    *,
    release_id: int,
    audience_type: str,
    listing_mode: str,
    requested_review_mode: str,
) -> dict:
    response = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers=headers,
        json={
            "audience_type": audience_type,
            "listing_mode": listing_mode,
            "install_mode": "enabled",
            "requested_review_mode": requested_review_mode,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_grant_token(
    session_factory,
    *,
    exposure_id: int,
    created_by_principal_id: int | None = None,
) -> str:
    from server.models import AccessGrant
    from server.modules.access import service as access_service

    with session_factory() as session:
        grant = AccessGrant(
            exposure_id=exposure_id,
            grant_type="link",
            subject_ref="search-contract-fixture",
            constraints_json="{}",
            state="active",
            created_by_principal_id=created_by_principal_id,
        )
        session.add(grant)
        session.flush()
        raw_token, _credential = access_service.create_grant_token(session, grant=grant)
        session.commit()
        return raw_token


def approve_exposure_review(
    client, session_factory, headers: dict[str, str], exposure_id: int
) -> None:
    from server.models import ReviewCase

    with session_factory() as session:
        review_case = session.scalar(
            select(ReviewCase).where(ReviewCase.exposure_id == exposure_id)
        )
        assert review_case is not None, f"expected review case for exposure {exposure_id}"
        review_case_id = review_case.id

    decision_response = client.post(
        f"/api/v1/review-cases/{review_case_id}/decisions",
        headers=headers,
        json={"decision": "approve", "note": "approved for search contract fixture"},
    )
    assert decision_response.status_code == 201, decision_response.text


def test_public_search_snapshot_results_include_install_resolution_targets() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-search-snapshot-test-"))
    try:
        artifact_root = configure_env(tmpdir)
        artifact_root.mkdir(parents=True, exist_ok=True)
        (artifact_root / "catalog").mkdir(parents=True, exist_ok=True)
        (artifact_root / "catalog" / "discovery-index.json").write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "name": "snapshot-skill",
                            "display_name": "Snapshot Skill",
                            "qualified_name": "partner/snapshot-skill",
                            "summary": "Snapshot skill summary",
                            "default_install_version": "1.2.3",
                            "latest_version": "1.2.3",
                            "runtime": {
                                "platform": "openclaw",
                                "readiness": {"ready": True, "status": "ready"},
                            },
                            "runtime_readiness": "ready",
                            "workspace_targets": ["skills", ".agents/skills"],
                            "match_names": [
                                "Snapshot Skill",
                                "snapshot-skill",
                                "partner/snapshot-skill",
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())

        response = client.get("/api/search?q=snapshot&scope=public")
        assert response.status_code == 200, response.text

        payload = response.json()
        skills = payload.get("skills") or []
        assert len(skills) == 1
        first = skills[0]
        assert first["name"] == "Snapshot Skill"
        assert first["qualified_name"] == "partner/snapshot-skill"
        assert first["install_scope"] == "public"
        assert first["install_ref"] == "partner/snapshot-skill@1.2.3"
        assert first["install_api_path"] == "/api/v1/install/public/partner/snapshot-skill@1.2.3"
        assert first["runtime"]["platform"] == "openclaw"
        assert first["runtime_readiness"] == "ready"
        assert first["workspace_targets"] == ["skills", ".agents/skills"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_me_search_results_include_install_resolution_targets_for_private_entries() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-search-me-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            headers,
            slug="private-search-skill",
            display_name="Private Search Skill",
        )
        private_exposure = create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )

        response = client.get(
            "/api/search?q=private-search&scope=me",
            headers=headers,
        )
        assert response.status_code == 200, response.text

        payload = response.json()
        skills = payload.get("skills") or []
        assert skills, payload
        private_entry = next(
            item
            for item in skills
            if item.get("qualified_name") == "fixture-maintainer/private-search-skill"
        )
        assert private_entry["audience_type"] == "private"
        assert private_entry["install_scope"] == "me"
        assert private_entry["install_ref"] == "fixture-maintainer/private-search-skill@0.1.0"
        assert (
            private_entry["install_api_path"]
            == "/api/v1/install/me/fixture-maintainer/private-search-skill@0.1.0"
        )
        assert private_entry["runtime"]["platform"] == "openclaw"
        assert private_entry["runtime_readiness"] == "ready"
        assert private_entry["workspace_targets"] == ["skills", ".agents/skills"]

        install_response = client.get(private_entry["install_api_path"], headers=headers)
        assert install_response.status_code == 200, install_response.text
        assert (
            install_response.json()["qualified_name"] == "fixture-maintainer/private-search-skill"
        )
        assert int(private_exposure["id"]) > 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_me_search_accepts_browser_session_cookie_authentication() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-search-cookie-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.auth import AUTH_COOKIE_NAME

        client = TestClient(create_app())
        token_headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            token_headers,
            slug="cookie-search-skill",
            display_name="Cookie Search Skill",
        )
        create_exposure(
            client,
            token_headers,
            release_id=release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )

        login_response = client.post(
            "/api/auth/login?lang=en", json={"token": "fixture-maintainer-token"}
        )
        assert login_response.status_code == 200, login_response.text
        assert login_response.json()["success"] is True
        session_cookie = login_response.cookies.get(AUTH_COOKIE_NAME)
        assert session_cookie, "expected login to issue a browser session cookie"

        client.cookies.set(AUTH_COOKIE_NAME, session_cookie)
        response = client.get("/api/search?q=cookie-search&scope=me")
        assert response.status_code == 200, response.text

        payload = response.json()
        skills = payload.get("skills") or []
        cookie_entry = next(
            item
            for item in skills
            if item.get("qualified_name") == "fixture-maintainer/cookie-search-skill"
        )
        assert cookie_entry["install_scope"] == "me"
        assert cookie_entry["audience_type"] == "private"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_grant_search_uses_grant_install_scope_for_grant_credentials() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-search-grant-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        release_id = create_ready_release(
            client,
            headers,
            slug="grant-search-skill",
            display_name="Grant Search Skill",
        )
        exposure = create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )
        grant_token = create_grant_token(session_factory, exposure_id=int(exposure["id"]))

        response = client.get(
            "/api/search?q=grant-search&scope=me",
            headers={"Authorization": f"Bearer {grant_token}"},
        )
        assert response.status_code == 200, response.text

        payload = response.json()
        skills = payload.get("skills") or []
        assert skills, payload
        grant_entry = next(
            item
            for item in skills
            if item.get("qualified_name") == "fixture-maintainer/grant-search-skill"
        )
        assert grant_entry["audience_type"] == "grant"
        assert grant_entry["install_scope"] == "grant"
        assert (
            grant_entry["install_api_path"]
            == "/api/v1/install/grant/fixture-maintainer/grant-search-skill@0.1.0"
        )
        assert grant_entry["runtime"]["platform"] == "openclaw"
        assert grant_entry["runtime_readiness"] == "ready"
        assert grant_entry["workspace_targets"] == ["skills", ".agents/skills"]

        explicit_grant_response = client.get(
            "/api/search?q=grant-search&scope=grant",
            headers={"Authorization": f"Bearer {grant_token}"},
        )
        assert explicit_grant_response.status_code == 200, explicit_grant_response.text
        explicit_skills = explicit_grant_response.json().get("skills") or []
        assert explicit_skills and explicit_skills[0]["install_scope"] == "grant"

        install_response = client.get(
            grant_entry["install_api_path"],
            headers={"Authorization": f"Bearer {grant_token}"},
        )
        assert install_response.status_code == 200, install_response.text
        assert install_response.json()["qualified_name"] == "fixture-maintainer/grant-search-skill"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
