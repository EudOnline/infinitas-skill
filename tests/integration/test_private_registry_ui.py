from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "server" / "app.py"
APP_JS_PATH = ROOT / "server" / "static" / "js" / "app.js"
AUTH_SESSION_JS_PATH = ROOT / "server" / "static" / "js" / "auth-session.js"
MODULES_DIR = ROOT / "server" / "static" / "js" / "modules"
SEARCH_MODULE_PATH = MODULES_DIR / "search.js"
LIFECYCLE_MODULE_PATH = MODULES_DIR / "lifecycle.js"
AUTH_HOME_MODULE_PATH = MODULES_DIR / "auth-home.js"
AUTH_CONSOLE_MODULE_PATH = MODULES_DIR / "auth-console.js"
AUTH_MODAL_MODULE_PATH = MODULES_DIR / "auth-modal.js"
ROUTES_PATH = ROOT / "server" / "ui" / "routes.py"
LAYOUT_TEMPLATE_PATH = ROOT / "server" / "templates" / "layout-kawaii.html"
LIBRARY_TEMPLATE_PATH = ROOT / "server" / "templates" / "library.html"
OBJECT_DETAIL_TEMPLATE_PATH = ROOT / "server" / "templates" / "object-detail.html"
ACCESS_CENTER_TEMPLATE_PATH = ROOT / "server" / "templates" / "access-center.html"
SHARES_TEMPLATE_PATH = ROOT / "server" / "templates" / "shares.html"
ACTIVITY_TEMPLATE_PATH = ROOT / "server" / "templates" / "activity.html"
RELEASE_DETAIL_V2_TEMPLATE_PATH = ROOT / "server" / "templates" / "release-detail-v2.html"
HOME_AUTH_PANEL_TEMPLATE_PATH = ROOT / "server" / "templates" / "partials" / "home-auth-panel.html"
SECURITY_PATH = ROOT / "server" / "middleware.py"
INPUT_CSS_PATH = ROOT / "server" / "static" / "css" / "input.css"
ALEMBIC_CONFIG_PATH = ROOT / "alembic.ini"
CONTROL_PLANE_BUSINESS_FLOWS_PATH = ROOT / "docs" / "guide" / "control-plane-business-flows.md"
FRONTEND_ALIGNMENT_PATH = ROOT / "docs" / "guide" / "frontend-control-plane-alignment.md"
FRONTEND_CHECKLIST_PATH = ROOT / "docs" / "guide" / "frontend-control-plane-checklist.md"
API_REFERENCE_PATH = ROOT / "docs" / "reference" / "api-reference.md"
APP_LINE_BUDGET = 220


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
            },
            {
                "username": "fixture-reviewer",
                "display_name": "Fixture Reviewer",
                "role": "maintainer",
                "token": "fixture-reviewer-token",
            },
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


def assert_route_composition_boundaries() -> None:
    routes_source = ROUTES_PATH.read_text(encoding="utf-8")
    routes_module = ast.parse(routes_source, filename=str(ROUTES_PATH))

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


def assert_maintained_control_plane_docs_freeze_canonical_model() -> None:
    docs = {
        CONTROL_PLANE_BUSINESS_FLOWS_PATH: CONTROL_PLANE_BUSINESS_FLOWS_PATH.read_text(encoding="utf-8"),
        FRONTEND_ALIGNMENT_PATH: FRONTEND_ALIGNMENT_PATH.read_text(encoding="utf-8"),
        FRONTEND_CHECKLIST_PATH: FRONTEND_CHECKLIST_PATH.read_text(encoding="utf-8"),
        API_REFERENCE_PATH: API_REFERENCE_PATH.read_text(encoding="utf-8"),
    }

    intros = {
        path: "\n".join(text.splitlines()[:20]).lower()
        for path, text in docs.items()
    }

    for path, intro in intros.items():
        assert "not maintained" in intro, (
            f"expected {path.name} intro to mark the old lifecycle model as not maintained"
        )
        assert "redirect" in intro or "migration shim" in intro, (
            f"expected {path.name} intro to describe legacy routes as redirects or migration shims"
        )

    for path, text in docs.items():
        assert "object/release/exposure/distribution" in text, (
            f"expected {path.name} to name object/release/exposure/distribution as the maintained model"
        )

    for route in ("/library", "/access", "/shares", "/activity"):
        assert route in docs[FRONTEND_ALIGNMENT_PATH], (
            f"expected frontend alignment guide to list maintained route {route}"
        )
        assert route in docs[FRONTEND_CHECKLIST_PATH], (
            f"expected frontend checklist to list maintained route {route}"
        )

    frontend_headings = "\n".join(
        line.strip().lower()
        for text in (
            docs[FRONTEND_ALIGNMENT_PATH],
            docs[FRONTEND_CHECKLIST_PATH],
        )
        for line in text.splitlines()
        if line.startswith("#")
    )

    for legacy_phrase in [
        "create skill",
        "create draft",
        "seal draft",
        "lifecycle console",
    ]:
        assert legacy_phrase not in frontend_headings, (
            "expected frontend alignment docs to keep legacy authoring terms out of maintained headings"
        )


def _slice_source(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _slice_top_level_function_source(source: str, start_marker: str) -> str:
    start = source.index(start_marker)
    search_from = start + len(start_marker)
    candidates = []
    for marker in (
        "\nasync function ",
        "\nfunction ",
        "\n// ============================================",
    ):
        idx = source.find(marker, search_from)
        if idx != -1:
            candidates.append(idx)
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def _sha256_base64(payload: str) -> str:
    return base64.b64encode(hashlib.sha256(payload.encode("utf-8")).digest()).decode("ascii")


def assert_private_registry_ui_js_contracts() -> None:
    app_js_source = APP_JS_PATH.read_text(encoding="utf-8")
    search_source = SEARCH_MODULE_PATH.read_text(encoding="utf-8")
    lifecycle_source = LIFECYCLE_MODULE_PATH.read_text(encoding="utf-8")
    library_template = LIBRARY_TEMPLATE_PATH.read_text(encoding="utf-8")
    object_detail_template = OBJECT_DETAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
    access_center_template = ACCESS_CENTER_TEMPLATE_PATH.read_text(encoding="utf-8")
    shares_template = SHARES_TEMPLATE_PATH.read_text(encoding="utf-8")
    activity_template = ACTIVITY_TEMPLATE_PATH.read_text(encoding="utf-8")
    release_detail_v2_template = RELEASE_DETAIL_V2_TEMPLATE_PATH.read_text(encoding="utf-8")
    auth_home_source = AUTH_HOME_MODULE_PATH.read_text(encoding="utf-8")
    auth_console_source = AUTH_CONSOLE_MODULE_PATH.read_text(encoding="utf-8")
    auth_modal_source = AUTH_MODAL_MODULE_PATH.read_text(encoding="utf-8")
    layout_template = LAYOUT_TEMPLATE_PATH.read_text(encoding="utf-8")
    home_auth_panel_template = HOME_AUTH_PANEL_TEMPLATE_PATH.read_text(encoding="utf-8")
    security_source = SECURITY_PATH.read_text(encoding="utf-8")
    create_draft_source = _slice_top_level_function_source(
        lifecycle_source,
        "async function createDraft(form) {",
    )
    install_panel_source = _slice_source(
        search_source,
        "  renderInstallPanel(data, skill) {",
        "\n\n  selectNext()",
    )
    artifacts_table_source = _slice_top_level_function_source(
        lifecycle_source,
        "async function updateArtifactsTable(releaseId) {",
    )
    access_check_source = _slice_top_level_function_source(
        lifecycle_source,
        "async function checkReleaseAccess(releaseId) {",
    )
    review_detail_source = _slice_top_level_function_source(
        lifecycle_source,
        "async function toggleReviewDetail(reviewCaseId, button) {",
    )
    exposure_policy_source = _slice_top_level_function_source(
        lifecycle_source,
        "function syncExposureReviewModePolicy() {",
    )
    release_poll_source = _slice_top_level_function_source(
        lifecycle_source,
        "async function pollReleaseReady(releaseId, intervalMs = 3000) {",
    )
    auth_handle_login_source = _slice_source(
        auth_modal_source,
        "  async function handleLogin() {",
        "\n  }\n\n  function setLoading(loading) {",
    )
    auth_init_home_source = _slice_source(
        auth_home_source,
        "export function initHomeAuthSession() {",
        "\n  init();\n}",
    )
    auth_console_login_success_source = _slice_source(
        auth_console_source,
        "  const controller = createAuthModalController({",
        "\n\n  async function init() {",
    )
    app_js_imports = set(
        re.findall(r"""from ['"](\./modules/[^'"]+)['"]""", app_js_source)
    )
    expected_shell_imports = {
        "./modules/toast.js",
        "./modules/theme.js",
        "./modules/search.js",
        "./modules/api.js",
        "./modules/table-interactions.js",
    }

    assert app_js_imports == expected_shell_imports, (
        "expected app.js to import only shared browser-shell modules after removing global "
        f"page-level bootstrap; got {sorted(app_js_imports)!r}"
    )

    for marker in [
        "new SearchManager()",
        "new ThemeManager()",
        "initSortableTable(table);",
        "initFilterableTable(table, filterInput);",
    ]:
        assert marker in app_js_source, (
            "expected the maintained browser shell bootstrap to keep only shared shell helpers; "
            f"missing marker {marker!r}"
        )

    for marker in [
        "initCreateSkill",
        "initCreateDraft",
        "initDraftDetail",
        "initReleaseDetail",
        "initShareDetail",
        "initAccessTokens",
        "initDelegatedActions",
        "setLifecycleToastRef",
        "./modules/lifecycle.js",
    ]:
        assert marker not in app_js_source, (
            "expected the maintained browser shell bootstrap to avoid legacy lifecycle "
            f"entrypoints and redundant release-admin wiring; found marker {marker!r}"
        )

    for template_source, marker in [
        (library_template, "static_url('/static/js/modules/library.js')"),
        (object_detail_template, "static_url('/static/js/modules/library.js')"),
        (access_center_template, "static_url('/static/js/modules/access-center.js')"),
        (shares_template, "static_url('/static/js/modules/shares.js')"),
        (activity_template, "static_url('/static/js/modules/activity.js')"),
        (release_detail_v2_template, "static_url('/static/js/modules/release-admin.js')"),
    ]:
        assert marker in template_source, (
            "expected maintained templates to own their page-level module wiring; "
            f"missing marker {marker!r}"
        )

    for marker in [
        "async function updateArtifactsTable(releaseId) {",
        "apiGet(`/api/v1/releases/${encodeURIComponent(releaseId)}/artifacts`)",
        "const artifacts = Array.isArray(data) ? data : (data.items || []);",
    ]:
        assert (
            marker in artifacts_table_source
            if marker != "async function updateArtifactsTable(releaseId) {"
            else marker in lifecycle_source
        ), (
            "expected release detail polling to refresh artifact rows from the release artifacts API; "
            f"missing marker {marker!r}"
        )
    for marker in [
        "_toast.error(uiText('invalid_json', 'JSON 格式错误'));",
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
        assert marker in search_source, (
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
        "const data = await apiGet(`/api/v1/releases/${encodeURIComponent(releaseId)}`, ac.signal);",
        "if (err.status === 403 || err.status === 404) {",
        "data.items || []",
    ]:
        assert (
            marker in lifecycle_source if marker == "data.items || []" else marker in release_poll_source
        ), (
            "expected release polling UI to update summary stats and recover from empty-state "
            f"artifact sections; missing marker {marker!r}"
        )
    next_target_index = auth_handle_login_source.index("const nextTarget = pendingRedirect;")
    close_modal_index = auth_handle_login_source.index("closeModal(")
    assert next_target_index < close_modal_index, (
        "expected auth login flow to snapshot pendingRedirect before closing the modal so "
        "protected navigation survives successful login"
    )
    for marker in [
        "const loginPanel = document.getElementById('login-panel');",
        "window.location.href = AUTH_SESSION_CONFIG.homeHref || '/';",
    ]:
        assert marker in auth_init_home_source, (
            "expected auth-session bootstrap to initialize the standalone /login page and "
            f"redirect after successful login; missing marker {marker!r}"
        )
    assert (
        "currentUser = { username: data.username, role: data.role || null };"
        in auth_console_login_success_source
    ), (
        "expected console auth success handler to refresh local session state immediately "
        "with the login response role"
    )
    for marker in [
        "const homeAuthModalStartsVisible = !standaloneLoginPage && controller.dom.modal && !controller.dom.modal.hidden;",
        "if (homeAuthModalStartsVisible) {",
        "openAuthModal();",
    ]:
        assert marker in auth_init_home_source, (
            "expected home auth bootstrap to explicitly sync a server-rendered visible modal "
            f"into the open modal controller state; missing marker {marker!r}"
        )
    assert "home-auth-session-bootstrap" not in home_auth_panel_template, (
        "expected home auth panel data bootstrap to avoid inline script tags so the "
        "page stays compatible with the CSP"
    )
    assert "style=" not in layout_template, (
        "expected layout-kawaii template to avoid inline style attributes under the current CSP"
    )
    assert "style=" not in object_detail_template, (
        "expected object-detail template to avoid inline style attributes under the current CSP"
    )
    assert ".style.colorScheme" not in search_source, (
        "expected app theme bootstrap to avoid writing inline style.colorScheme under the CSP"
    )
    assert ".style.colorScheme" not in layout_template, (
        "expected inline theme bootstrap to avoid writing inline style.colorScheme under the CSP"
    )
    layout_script = re.search(r"<script>(.*?)</script>", layout_template, re.S)
    layout_style = re.search(r"<style>(.*?)</style>", layout_template, re.S)
    assert layout_script is not None, (
        "expected layout-kawaii template to keep a single inline theme bootstrap"
    )
    assert layout_style is not None, (
        "expected layout-kawaii template to keep the inline critical CSS block"
    )
    assert _sha256_base64(layout_script.group(1)) in security_source, (
        "expected CSP script-src hashes to match the current inline theme bootstrap"
    )
    assert _sha256_base64(layout_style.group(1)) in security_source, (
        "expected CSP style-src hashes to match the current inline critical CSS block"
    )
    assert "/static/js/deco-effects.js" not in layout_template, (
        "expected layout-kawaii template to avoid loading decorative runtime scripts that "
        "mutate inline styles under the CSP"
    )


def assert_home_auth_modal_initial_state_is_explicit() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-ui-auth-modal-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        assert response.status_code == 200, response.text
        html = response.text

        auth_modal = re.search(r'<div class="auth-modal" id="auth-modal"([^>]*)>', html)
        assert auth_modal is not None, "expected home page to render the auth modal"
        assert "hidden" not in auth_modal.group(1), (
            "expected anonymous home auth modal to render explicitly open instead of relying "
            "on CSS to override the hidden attribute"
        )

        auth_error = re.search(r'<div class="auth-error" id="auth-error"([^>]*)>', html)
        assert auth_error is not None, "expected home page to render the auth error container"
        assert "hidden" in auth_error.group(1), (
            "expected the auth error banner to stay hidden until login actually fails"
        )

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def assert_auth_hidden_states_are_preserved_in_css() -> None:
    css_source = INPUT_CSS_PATH.read_text(encoding="utf-8")
    for marker in [
        ".auth-modal[hidden]",
        ".console-auth-modal[hidden]",
        ".auth-error[hidden]",
        ".console-auth-modal__error[hidden]",
    ]:
        assert marker in css_source, (
            "expected auth UI styles to preserve the hidden attribute for modals and "
            f"error banners; missing marker {marker!r}"
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

    reviewer_headers = {"Authorization": "Bearer fixture-reviewer-token"}
    decision_response = client.post(
        f"/api/v1/review-cases/{review_case_id}/decisions",
        headers=reviewer_headers,
        json={"decision": "approve", "note": "approved for ui fixture"},
    )
    assert decision_response.status_code == 201, decision_response.text


def assert_ui_rejects_untrusted_host_headers() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-ui-host-test-"))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        poisoned = client.get("/login?lang=en", headers={"host": "skills.example.com"})
        assert poisoned.status_code == 400, poisoned.text
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_server_app_delegates_html_routes_and_respects_size_budget() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_composition_boundaries()
    assert_template_response_request_first()
    assert_alembic_config_declares_path_separator()


def test_maintained_control_plane_docs_freeze_canonical_model() -> None:
    assert_maintained_control_plane_docs_freeze_canonical_model()


def test_private_first_console_ui_round_trip() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-library-cutover-test-"))
    try:
        configure_env(tmpdir)
        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        headers = {"Authorization": "Bearer fixture-maintainer-token"}

        login_response = client.get("/login?lang=en")
        assert login_response.status_code == 200, login_response.text
        assert "/library" in login_response.text
        assert "/skills" not in login_response.text

        library_response = client.get("/library?lang=en", headers=headers)
        assert library_response.status_code == 200, library_response.text
        assert "Library" in library_response.text

        skills_response = client.get("/skills?lang=en", headers=headers, follow_redirects=False)
        assert skills_response.status_code == 307
        assert skills_response.headers["location"] == "/manage?lang=en"

        review_response = client.get(
            "/review-cases?lang=en",
            headers=headers,
            follow_redirects=False,
        )
        assert review_response.status_code == 307
        assert review_response.headers["location"] == "/manage?lang=en#activity"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_private_registry_ui_rejects_untrusted_host_headers() -> None:
    assert_ui_rejects_untrusted_host_headers()


def test_private_registry_ui_js_contracts_cover_access_and_install_panels() -> None:
    assert_private_registry_ui_js_contracts()


def test_home_auth_modal_initial_state_is_explicit() -> None:
    assert_home_auth_modal_initial_state_is_explicit()


def test_auth_hidden_states_are_preserved_in_css() -> None:
    assert_auth_hidden_states_are_preserved_in_css()


def main() -> None:
    assert_ui_route_registration_boundary()
    assert_app_size_budget()
    assert_route_composition_boundaries()
    assert_template_response_request_first()
    assert_alembic_config_declares_path_separator()
    test_private_first_console_ui_round_trip()
    assert_ui_rejects_untrusted_host_headers()
    assert_private_registry_ui_js_contracts()
    assert_home_auth_modal_initial_state_is_explicit()
    assert_auth_hidden_states_are_preserved_in_css()
