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
APP_JS_PATH = ROOT / "server" / "static" / "js" / "app.js"
ROUTES_PATH = ROOT / "server" / "ui" / "routes.py"
LIFECYCLE_PATH = ROOT / "server" / "ui" / "lifecycle.py"
ALEMBIC_CONFIG_PATH = ROOT / "alembic.ini"
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


def assert_template_response_request_first() -> None:
    module = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))
    invalid_calls: list[int] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "TemplateResponse":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            invalid_calls.append(node.lineno)
    assert not invalid_calls, (
        "expected all TemplateResponse calls in server.ui.routes to pass request as the "
        f"first positional argument; found legacy calls on lines {invalid_calls}"
    )


def assert_alembic_config_declares_path_separator() -> None:
    config_text = ALEMBIC_CONFIG_PATH.read_text(encoding="utf-8")
    assert "path_separator = os" in config_text, (
        "expected alembic.ini to declare path_separator = os so prepend_sys_path avoids "
        "legacy splitting deprecation warnings"
    )


def _slice_source(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def assert_private_registry_ui_js_contracts() -> None:
    source = APP_JS_PATH.read_text(encoding="utf-8")
    create_draft_source = _slice_source(
        source,
        "async function createDraft(form) {",
        "\n}\n\nasync function saveDraft(form) {",
    )
    install_panel_source = _slice_source(
        source,
        "  renderInstallPanel(data, skill) {",
        "\n\n  selectNext()",
    )
    access_check_source = _slice_source(
        source,
        "async function checkReleaseAccess(releaseId) {",
        "\n}\n\n// ============================================",
    )
    review_detail_source = _slice_source(
        source,
        "async function toggleReviewDetail(reviewCaseId, button) {",
        "\n}\n\nfunction renderReviewDetail(container, data) {",
    )
    exposure_policy_source = _slice_source(
        source,
        "function syncExposureReviewModePolicy() {",
        "\n}\n\nfunction initReviewCases() {",
    )
    release_poll_source = _slice_source(
        source,
        "async function pollReleaseReady(releaseId, intervalMs = 3000) {",
        "\n}\n\nasync function createExposure(form) {",
    )

    assert "/api/v1/releases/${releaseId}/artifacts" in source, (
        "expected release detail polling to refresh artifact rows from the release artifacts API"
    )
    for marker in [
        "toast.error(uiText('invalid_json', 'JSON 格式错误'));",
        "setButtonLoading(button, false);",
        "return;",
    ]:
        assert marker in create_draft_source, (
            "expected create-draft flow to block invalid metadata JSON instead of silently "
            f"submitting an empty payload; missing marker {marker!r}"
        )
    for marker in [
        "const policy = release.exposure_policy[audienceType] || null;",
        "reviewModeSelect.disabled = false;",
        "reviewModeSelect.value = policy.effective_requested_review_mode;",
        "publicWarning.hidden = audienceType !== 'public';",
    ]:
        assert marker in exposure_policy_source, (
            "expected share detail UI to sync requested review mode with backend-provided "
            f"audience policy; missing marker {marker!r}"
        )
    for marker in [
        "data.publisher || '-'",
        "formatInstallScope(skill.install_scope || data.install_scope)",
        "formatListingMode(skill.listing_mode || data.listing_mode)",
        "data.bundle_sha256 || '-'",
    ]:
        assert marker in install_panel_source, (
            "expected install panel to expose publisher, install scope, listing mode, "
            f"and bundle sha fields; missing marker {marker!r}"
        )
    for marker in [
        "me: { zh: '仅自己', en: 'Only me' }",
        "grant: { zh: '授权', en: 'Grant' }",
        "direct_only: { zh: '仅直链', en: 'Direct only' }",
    ]:
        assert marker in source, (
            "expected install panel formatters to humanize install scope and listing mode; "
            f"missing marker {marker!r}"
        )
    for marker in [
        "data.ok",
        "data.credential_type",
        "data.principal_id",
        "data.scope_granted",
        "access_denied",
    ]:
        assert marker in access_check_source, (
            "expected release access check UI to render the backend response fields and "
            f"retain denied-state handling; missing marker {marker!r}"
        )
    for marker in [
        "opened = true",
        "review_detail_history",
        "review_detail_hide",
    ]:
        assert marker in review_detail_source, (
            "expected review detail toggle flow to keep localized History/Hide labels in sync; "
            f"missing marker {marker!r}"
        )
    for marker in [
        "const artifactCount = await updateArtifactsTable(releaseId);",
        ".page-stats .stat",
        "valueEl.textContent = readyText;",
        "valueEl.textContent = String(artifactCount || 0);",
        "const data = await apiGet(`/api/v1/releases/${releaseId}`, controller.signal);",
        "if (err.status === 403 || err.status === 404) {",
        "data.items || []",
    ]:
        assert marker in source if marker == "data.items || []" else marker in release_poll_source, (
            "expected release polling UI to update summary stats and recover from empty-state "
            f"artifact sections; missing marker {marker!r}"
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
        from server.worker import run_worker_loop

        client = TestClient(create_app())
        session_factory = get_session_factory()
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        # 1) Create skill through API (UI will verify forms exist)
        create_skill_response = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "console-ui-skill",
                "display_name": "Console UI Skill",
                "summary": "A skill for UI testing",
            },
        )
        assert create_skill_response.status_code == 201, create_skill_response.text
        skill_id = int(create_skill_response.json()["id"])

        # 2) Verify skills page has create-skill form
        skills_response = client.get("/skills?lang=en", headers=headers)
        assert skills_response.status_code == 200, skills_response.text
        skills_html = skills_response.text
        for label in ["Skills", "Drafts", "Releases", "Share", "Access", "Review"]:
            assert label in skills_html
        assert 'id="create-skill-form"' in skills_html

        # 3) Create draft and verify skill detail has create-draft form
        create_draft_response = client.post(
            f"/api/v1/skills/{skill_id}/drafts",
            headers=headers,
            json={
                "content_ref": "git+https://example.com/repo.git#0123456789abcdef0123456789abcdef01234567",
                "metadata": {"entrypoint": "SKILL.md"},
            },
        )
        assert create_draft_response.status_code == 201, create_draft_response.text
        draft_id = int(create_draft_response.json()["id"])

        skill_detail_response = client.get(f"/skills/{skill_id}?lang=en", headers=headers)
        assert skill_detail_response.status_code == 200, skill_detail_response.text
        skill_detail_html = skill_detail_response.text
        assert 'id="create-draft-form"' in skill_detail_html

        # 4) Verify draft detail has edit and seal forms while open
        draft_detail_response = client.get(f"/drafts/{draft_id}?lang=en", headers=headers)
        assert draft_detail_response.status_code == 200, draft_detail_response.text
        draft_detail_html = draft_detail_response.text
        assert 'id="save-draft-form"' in draft_detail_html
        assert 'id="seal-draft-form"' in draft_detail_html

        # 5) Seal draft
        seal_response = client.post(
            f"/api/v1/drafts/{draft_id}/seal",
            headers=headers,
            json={"version": "0.1.0"},
        )
        assert seal_response.status_code == 201, seal_response.text
        version_id = int((seal_response.json().get("skill_version") or {})["id"])

        # 6) Verify sealed draft is read-only and skill detail has create-release buttons
        sealed_draft_response = client.get(f"/drafts/{draft_id}?lang=en", headers=headers)
        assert sealed_draft_response.status_code == 200, sealed_draft_response.text
        sealed_draft_html = sealed_draft_response.text
        assert 'id="save-draft-form"' not in sealed_draft_html
        assert 'id="seal-draft-form"' not in sealed_draft_html

        skill_detail_after_seal = client.get(f"/skills/{skill_id}?lang=en", headers=headers)
        skill_detail_after_seal_html = skill_detail_after_seal.text
        assert 'data-action="create-release"' in skill_detail_after_seal_html

        # 7) Create release and verify preparing state on detail page
        create_release_response = client.post(
            f"/api/v1/versions/{version_id}/releases",
            headers=headers,
        )
        assert create_release_response.status_code == 201, create_release_response.text
        release_id = int(create_release_response.json()["id"])

        release_detail_response = client.get(f"/releases/{release_id}?lang=en", headers=headers)
        assert release_detail_response.status_code == 200, release_detail_response.text
        release_detail_html = release_detail_response.text
        assert "preparing" in release_detail_html or "Pending" in release_detail_html or "pending" in release_detail_html.lower()
        assert 'id="release-status"' in release_detail_html
        assert 'id="artifact-section"' in release_detail_html

        # 8) Run worker to materialize release
        processed = run_worker_loop(limit=1)
        assert processed == 1, f"expected worker to process 1 release job, got {processed}"

        # 9) Verify ready state
        release_ready_response = client.get(f"/releases/{release_id}?lang=en", headers=headers)
        assert release_ready_response.status_code == 200, release_ready_response.text
        release_ready_html = release_ready_response.text
        assert "ready" in release_ready_html.lower() or "Ready" in release_ready_html or "success" in release_ready_html.lower()
        for label in ["Manifest", "Bundle", "Provenance", "Signature"]:
            assert label in release_ready_html

        access_response = client.get("/access/tokens?lang=en", headers=headers)
        assert access_response.status_code == 200, access_response.text
        access_html = access_response.text
        for label in [
            "Current identity",
            "Release access check",
            "Release ID",
            "Principal",
            "Scopes",
        ]:
            assert label in access_html

        # 10) Verify share page has exposure creation form
        share_response = client.get(f"/releases/{release_id}/share?lang=en", headers=headers)
        assert share_response.status_code == 200, share_response.text
        share_html = share_response.text
        assert 'id="create-exposure-form"' in share_html
        for label in ["Private", "Shared by token", "Public"]:
            assert label in share_html

        # 11) Create exposures via API and verify UI actions
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

        # Verify share page shows exposure actions
        share_with_exposures = client.get(f"/releases/{release_id}/share?lang=en", headers=headers)
        share_with_html = share_with_exposures.text
        public_exposure_id = int(public_exposure["id"])
        public_exposure_row = None
        for row in share_with_html.split("<tr>"):
            if f"<td>#{public_exposure_id}</td>" in row:
                public_exposure_row = row
                break
        assert public_exposure_row is not None, "public exposure row not found in share page"
        assert 'data-action="activate-exposure"' not in public_exposure_row
        assert (
            "Activation blocked: review must be approved first" in public_exposure_row
            or "需要审核通过后才能激活" in public_exposure_row
        )
        assert 'data-action="revoke-exposure"' in share_with_html
        assert 'data-action="patch-exposure"' in share_with_html

        # 12) Verify review cases page shows actionable controls including comment
        review_response = client.get("/review-cases?lang=en", headers=headers)
        assert review_response.status_code == 200, review_response.text
        review_html = review_response.text
        assert 'data-action="review-approve"' in review_html
        assert 'data-action="review-reject"' in review_html
        assert 'data-action="review-comment"' in review_html
        assert 'data-action="review-detail"' in review_html
        assert "review-detail-row" in review_html
        assert 'id="review-detail-content-' in review_html

        # 13) Approve review and verify exposure becomes active
        approve_exposure_review(client, session_factory, headers, int(public_exposure["id"]))

        share_after_approval = client.get(f"/releases/{release_id}/share?lang=en", headers=headers)
        share_after_html = share_after_approval.text
        assert "active" in share_after_html.lower() or "Active" in share_after_html

        home_html = client.get("/").text
        assert "私人技能库" in home_html
        for marker in ['id="user-panel-login"', 'id="open-auth-modal-btn"']:
            assert marker in home_html
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_server_app_delegates_html_routes_and_respects_size_budget() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_and_lifecycle_composition_boundaries()
    assert_lifecycle_size_budget()
    assert_template_response_request_first()
    assert_alembic_config_declares_path_separator()


def test_private_first_console_ui_round_trip() -> None:
    assert_private_first_console_ui_round_trip()


def test_private_registry_ui_js_contracts_cover_access_and_install_panels() -> None:
    assert_private_registry_ui_js_contracts()


def main() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_and_lifecycle_composition_boundaries()
    assert_lifecycle_size_budget()
    assert_template_response_request_first()
    assert_alembic_config_declares_path_separator()
    assert_private_first_console_ui_round_trip()
    assert_private_registry_ui_js_contracts()
