from __future__ import annotations

import ast
import json
import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "server" / "app.py"
ROUTES_PATH = ROOT / "server" / "ui" / "routes.py"
LIFECYCLE_PATH = ROOT / "server" / "ui" / "lifecycle.py"
APP_LINE_BUDGET = 220
LIFECYCLE_LINE_BUDGET = 500


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
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


def assert_ui_route_registration_boundary() -> None:
    module = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    imported = False
    delegated = False
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == "server.ui.routes":
            if any(alias.name == "register_ui_routes" for alias in node.names):
                imported = True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_ui_routes"
        ):
            delegated = True
    assert imported and delegated, (
        "expected server.app to import and call register_ui_routes from server.ui.routes"
    )


def assert_app_size_budget() -> None:
    line_count = len(APP_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count <= APP_LINE_BUDGET, (
        f"expected server/app.py to stay within {APP_LINE_BUDGET} lines after UI extraction, got {line_count}"
    )


def assert_route_and_lifecycle_composition_boundaries() -> None:
    routes_source = ROUTES_PATH.read_text(encoding="utf-8")
    routes_module = ast.parse(routes_source, filename=str(ROUTES_PATH))
    lifecycle_module = ast.parse(
        LIFECYCLE_PATH.read_text(encoding="utf-8"), filename=str(LIFECYCLE_PATH)
    )

    imported_session_bootstrap = False
    imported_navigation = False
    imported_auth_state = False
    called_session_bootstrap = False
    for node in ast.walk(routes_module):
        if isinstance(node, ast.ImportFrom) and node.module == "server.ui.session_bootstrap":
            if any(alias.name == "build_session_bootstrap" for alias in node.names):
                imported_session_bootstrap = True
        if isinstance(node, ast.ImportFrom) and node.module == "server.ui.navigation":
            if any(alias.name == "build_site_nav" for alias in node.names):
                imported_navigation = True
        if isinstance(node, ast.ImportFrom) and node.module == "server.ui.auth_state":
            auth_aliases = {
                "is_owner",
                "require_draft_bundle_or_404",
                "require_lifecycle_actor",
                "require_release_bundle_or_404",
                "require_skill_or_404",
            }
            if any(alias.name in auth_aliases for alias in node.names):
                imported_auth_state = True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_session_bootstrap"
        ):
            called_session_bootstrap = True

    lifecycle_imports = {
        node.module
        for node in ast.walk(lifecycle_module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert imported_session_bootstrap and called_session_bootstrap, (
        "expected server.ui.routes to import and call build_session_bootstrap"
    )
    assert imported_navigation, (
        "expected server.ui.routes to import build_site_nav from server.ui.navigation"
    )
    assert imported_auth_state, (
        "expected server.ui.routes to import auth helpers from server.ui.auth_state"
    )
    assert 'context["session_ui"]["current_user"]' not in routes_source, (
        "expected server.ui.routes to avoid manually mutating session_ui.current_user"
    )
    assert "server.ui.navigation" in lifecycle_imports, (
        "expected server.ui.lifecycle to compose navigation helpers"
    )
    assert "server.ui.notifications" in lifecycle_imports, (
        "expected server.ui.lifecycle to compose notification helpers"
    )


def assert_lifecycle_size_budget() -> None:
    line_count = len(LIFECYCLE_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count <= LIFECYCLE_LINE_BUDGET, (
        "expected server/ui/lifecycle.py to stay within "
        f"{LIFECYCLE_LINE_BUDGET} lines after UI extraction, got {line_count}"
    )


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
            "metadata": {
                "entrypoint": "SKILL.md",
                "language": "zh-CN",
                "manifest": {"name": slug, "version": "0.1.0"},
            },
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
        json={"decision": "approve", "note": "approved for ui fixture"},
    )
    assert decision_response.status_code == 201, decision_response.text


def assert_private_first_console_ui_round_trip() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-ui-test-"))
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
            slug="console-ui-skill",
            display_name="Console UI Skill",
        )

        create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="private",
            listing_mode="direct_only",
            requested_review_mode="none",
        )
        create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="grant",
            listing_mode="listed",
            requested_review_mode="none",
        )
        public_exposure = create_exposure(
            client,
            headers,
            release_id=release_id,
            audience_type="public",
            listing_mode="listed",
            requested_review_mode="none",
        )
        approve_exposure_review(client, session_factory, headers, int(public_exposure["id"]))

        home_html = client.get("/").text
        assert "私人技能库" in home_html
        for marker in ['id="user-panel-login"', 'id="open-auth-modal-btn"']:
            assert marker in home_html

        skills_response = client.get("/skills?lang=en", headers=headers)
        assert skills_response.status_code == 200, skills_response.text
        skills_html = skills_response.text
        for label in ["Skills", "Drafts", "Releases", "Share", "Access", "Review"]:
            assert label in skills_html

        share_response = client.get(f"/releases/{release_id}/share?lang=en", headers=headers)
        assert share_response.status_code == 200, share_response.text
        share_html = share_response.text
        for label in ["Private", "Shared by token", "Public"]:
            assert label in share_html
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_server_app_delegates_html_routes_and_respects_size_budget() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_and_lifecycle_composition_boundaries()
    assert_lifecycle_size_budget()


def test_private_first_console_ui_round_trip() -> None:
    assert_private_first_console_ui_round_trip()


def main() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_and_lifecycle_composition_boundaries()
    assert_lifecycle_size_budget()
    assert_private_first_console_ui_round_trip()
