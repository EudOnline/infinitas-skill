#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


from server.artifact_ops import sync_catalog_artifacts


def fail(message: str):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_bootstrap_payload(html: str, element_id: str) -> dict:
    match = re.search(rf'id="{re.escape(element_id)}"[^>]*data-json="([^"]*)"', html)
    if not match:
        fail(f"expected page to embed bootstrap payload in #{element_id}")
    try:
        return json.loads(unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        fail(f"failed to parse bootstrap payload from #{element_id}: {exc}")
    return {}


def read_stylesheet(href: str) -> str:
    href = href.split("?", 1)[0]
    if not href.startswith("/static/"):
        fail(f"expected stylesheet href to be a local /static asset, got {href}")
    path = ROOT / "server" / href.lstrip("/")
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"expected stylesheet asset to exist at {path}")
    return ""


def page_css(html: str) -> str:
    hrefs = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
    if not hrefs:
        fail("expected page to link at least one stylesheet")
    return "\n".join(read_stylesheet(href) for href in hrefs if href.startswith("/static/"))


def configure_env(tmpdir: Path):
    from server.db import get_engine, get_session_factory
    from server.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
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
    os.environ.pop("INFINITAS_REGISTRY_READ_TOKENS", None)


def scenario_home_uses_kawaii_theme_with_live_context():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-theme-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        session_bootstrap = parse_bootstrap_payload(html, "app-session-data")
        checks = [
            ("kawaii theme root attribute", 'data-theme="kawaii"' in html),
            ("kawaii layout topbar present", 'class="topbar animate-in"' in html),
            ("kawaii layout topbar controls present", 'class="topbar-side ' in html),
            ("kawaii layout shell present", 'id="main-content"' in html),
            ("kawaii layout language toggles present", "/?lang=" in html),
            ("home anchor nav start", 'href="#start"' in html),
            ("home anchor nav handoff", 'href="#handoff"' in html),
            ("home anchor nav console", 'href="#console"' in html),
            ("no broken skills nav on home", 'href="/skills"' not in html),
            (
                "auth modal uses dialog semantics",
                'role="dialog"' in html
                and 'aria-modal="true"' in html
                and 'aria-labelledby="auth-modal-title"' in html,
            ),
            ("user trigger exposes controlled panel", 'aria-controls="user-panel"' in html),
            (
                "status chip mode present",
                re.search(
                    r'<span class="status-chip"><span aria-hidden="true">🔒</span>\s*模式</span>',
                    html,
                )
                is not None,
            ),
            (
                "status chip sync present",
                re.search(
                    r'<span class="status-chip"><span aria-hidden="true">📅</span>\s*同步</span>',
                    html,
                )
                is not None,
            ),
            (
                "status chip flow present",
                re.search(
                    r'<span class="status-chip"><span aria-hidden="true">⚡</span>\s*流转</span>',
                    html,
                )
                is not None,
            ),
            (
                "anonymous app session exposes cookie hint flag",
                session_bootstrap.get("has_auth_cookie_hint") is False,
            ),
            (
                "anonymous app session omits current user bootstrap",
                "current_user" not in session_bootstrap,
            ),
        ]
        if "/v2" in html:
            fail("home page should not reference /v2 after kawaii cutover")
        failures = [label for label, passed in checks if not passed]
        if failures:
            fail(f"home page did not satisfy kawaii homepage expectations: {', '.join(failures)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_uses_refined_kawaii_presentation():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-refined-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        banned_markers = [
            "-webkit-text-fill-color: transparent",
            "--ease-bounce",
            "--ease-elastic",
            "document.addEventListener('mousemove'",
            "createSparkle(",
            "@keyframes sparklePop",
        ]
        present = [marker for marker in banned_markers if marker in html]
        if present:
            fail(f"home page still contains unrefined presentation markers: {', '.join(present)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_supports_readable_copy_and_mobile_adaptation():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-mobile-readable-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        css = page_css(html)
        source_css = (ROOT / "server/static/css/input.css").read_text(encoding="utf-8")
        required_snippets = [
            "--kawaii-ink-soft: #64637d",
            "--kawaii-ink-muted: #7c7b92",
            "overflow-wrap: anywhere;",
            "min-width: 0;",
        ]
        missing_snippets = [
            snippet
            for snippet in required_snippets
            if snippet not in css and snippet not in source_css
        ]
        if missing_snippets:
            fail(
                f"home page is missing readability hardening markers: {', '.join(missing_snippets)}"
            )

        mobile_checks = [
            ("hero CTA has responsive class hook", 'class="hero-cta ' in html),
            (
                "section CTA fills mobile width",
                ".section-action {\n      width: 100%;" in source_css,
            ),
            (
                "section button fills mobile width",
                ".section-action .kawaii-button {\n      width: 100%;" in source_css,
            ),
            (
                "console grid has mobile rule",
                ".console-grid {\n      grid-template-columns: repeat(2, minmax(0, 1fr));"
                in source_css,
            ),
            (
                "skills grid uses responsive tailwind layout",
                "skills-grid flex gap-3 overflow-x-auto snap-x" in html,
            ),
        ]
        missing_mobile = [label for label, passed in mobile_checks if not passed]
        if missing_mobile:
            fail(f"home page is missing mobile adaptation rules: {', '.join(missing_mobile)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_polish_tightens_rhythm_and_clarifies_ctas():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-polish-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        source_css = (ROOT / "server/static/css/input.css").read_text(encoding="utf-8")
        spacing_checks = [
            ("desktop hero spacing set", "hero-section mb-4 md:mb-3.5" in html),
            ("desktop status spacing set", "status-section mb-2.5 md:mb-3" in html),
            (
                "desktop console spacing set",
                ".console-section {\n    margin-bottom: 1rem;" in source_css,
            ),
            (
                "section topline spacing set",
                ".section-topline {\n    display: flex;" in source_css
                and "margin-bottom: 0.75rem;" in source_css,
            ),
        ]
        missing_spacing = [label for label, passed in spacing_checks if not passed]
        if missing_spacing:
            fail(f"home page is missing final rhythm polish markers: {', '.join(missing_spacing)}")

        required_copy = [
            "复制任务提示",
            "打开对象库",
            "检查细节",
            "快速开始",
            "常用技能",
        ]
        missing_copy = [label for label in required_copy if label not in html]
        if missing_copy:
            fail(f"home page is missing clearer CTA copy: {', '.join(missing_copy)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_supports_manual_theme_and_language_switches():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-switches-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        zh_response = client.get("/")
        en_response = client.get("/?lang=en")
        if zh_response.status_code != 200:
            fail(f"expected GET / to return 200, got {zh_response.status_code}: {zh_response.text}")
        if en_response.status_code != 200:
            fail(
                f"expected GET /?lang=en to return 200, got {en_response.status_code}: {en_response.text}"
            )

        zh_html = zh_response.text
        en_html = en_response.text

        required_theme_markers = [
            'data-theme-choice="light"',
            'data-theme-choice="dark"',
            'html[data-color-scheme="dark"]',
        ]
        missing_theme = [marker for marker in required_theme_markers if marker not in zh_html]
        if missing_theme:
            fail(f"home page is missing manual theme controls: {', '.join(missing_theme)}")

        zh_markers = [
            '<html lang="zh-CN"',
            "浅色",
            "深色",
            "中",
            ">EN<",
        ]
        missing_zh = [marker for marker in zh_markers if marker not in zh_html]
        if missing_zh:
            fail(f"home page is missing chinese toggle labels: {', '.join(missing_zh)}")

        en_markers = [
            '<html lang="en"',
            "Copy task prompt",
            "Open Library",
            "Light",
            "Dark",
            "Home base",
        ]
        missing_en = [marker for marker in en_markers if marker not in en_html]
        if missing_en:
            fail(f"home page is missing english rendering markers: {', '.join(missing_en)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_english_copy_stays_english_and_preserves_lang_routes():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-en-i18n-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/?lang=en")
        if response.status_code != 200:
            fail(
                f"expected GET /?lang=en to return 200, got {response.status_code}: {response.text}"
            )

        html = response.text
        required_strings = [
            "<title>infinitas private skill library</title>",
            'content="infinitas - a private-first agent skill library for authoring, release, sharing, and install"',
            "Quick start",
            "Authentication",
            "Enter your account details.",
            "Enter username",
            "Enter password",
            "Username and password",
            ">Cancel<",
            ">Verify<",
            "Inspect details",
            'aria-label="Main"',
            'aria-label="Nav"',
            "Sakura Street",
            "Starry Night",
        ]
        missing_strings = [marker for marker in required_strings if marker not in html]
        if missing_strings:
            fail(f"english home page is missing localized ui copy: {', '.join(missing_strings)}")

        unexpected_chinese_bg_names = ["樱花街道", "动漫天空", "星空夜景", "赛博朋克"]
        present_chinese_bg_names = [
            marker for marker in unexpected_chinese_bg_names if marker in html
        ]
        if present_chinese_bg_names:
            fail(
                f"english home page should not embed chinese-only background preset names: {', '.join(present_chinese_bg_names)}"
            )
        if 'aria-label="主内容"' in html:
            fail("english home page should not keep chinese main landmark labels")

        required_href_markers = [
            'href="/?lang=en"',
            'data-auth-target="/library?lang=en"',
            'data-auth-target="/access?lang=en"',
            'data-auth-target="/shares?lang=en"',
            'data-auth-target="/activity?lang=en"',
        ]
        missing_hrefs = [marker for marker in required_href_markers if marker not in html]
        if missing_hrefs:
            fail(
                f"english home page is missing language-preserving navigation markers: {', '.join(missing_hrefs)}"
            )

        search_markers = [
            'placeholder="Search..."',
            'aria-label="Results"',
        ]
        missing_search = [marker for marker in search_markers if marker not in html]
        if missing_search:
            fail(
                f"english home page is missing localized search accessibility markers: {', '.join(missing_search)}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_chinese_copy_stays_chinese_in_primary_chrome():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-zh-i18n-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        required_strings = [
            "私人技能工作台",
            "复制任务提示",
            "打开对象库",
            "<title>infinitas 私人技能库</title>",
            'content="infinitas - 小二的私人技能库，覆盖技能创作、发布、分享与安装"',
            'aria-label="主内容"',
            'aria-label="导航"',
        ]
        missing_strings = [marker for marker in required_strings if marker not in html]
        if missing_strings:
            fail(
                f"chinese home page is missing localized primary chrome copy: {', '.join(missing_strings)}"
            )

        unexpected_strings = [
            "Private agent workspace / 私人技能工作台",
            "Private agent workspace / personal skill desk",
            "<title>infinitas hosted registry</title>",
        ]
        present_unexpected = [marker for marker in unexpected_strings if marker in html]
        if present_unexpected:
            fail(
                "chinese home page should avoid mixed-language primary chrome copy, found: "
                + ", ".join(present_unexpected)
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_chinese_auth_copy_uses_access_token_terms():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-zh-auth-copy-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        required_strings = [
            "请输入账户信息。",
            "输入用户名",
            "输入密码",
            "用户名和密码",
            "用户名或密码错误",
        ]
        missing_strings = [marker for marker in required_strings if marker not in html]
        if missing_strings:
            fail(
                f"chinese home auth UI is missing username/password wording: {', '.join(missing_strings)}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_mobile_touch_targets_stay_thumb_friendly():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-touch-targets-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        css = page_css(response.text)
        required_patterns = {
            "mobile nav links reserve 44px touch height": (
                r"\.nav a\s*\{[^}]*min-height:\s*2\.75rem;"
            ),
            "theme and language chips reserve 44px touch height": (
                r"\.toggle-chip\s*\{[^}]*min-height:\s*2\.75rem;"
            ),
            "quick-start pills reserve 44px touch height": (
                r"\.quick-pill\s*\{[^}]*min-height:\s*2\.75rem;"
            ),
            "copy buttons reserve 44px touch height": (
                r"\.skill-copy\s*\{[^}]*min-height:\s*2\.75rem;"
            ),
        }
        missing = [
            label
            for label, pattern in required_patterns.items()
            if not re.search(pattern, css, re.S)
        ]
        if missing:
            fail(
                f"home page is missing mobile touch target hardening markers: {', '.join(missing)}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_auth_controls_keep_thumb_friendly_targets():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-auth-controls-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        css = page_css(response.text)
        required_patterns = {
            "auth modal close button keeps a 44px square target": (
                r"\.auth-modal-close\s*\{[^}]*width:\s*2\.75rem;[^}]*height:\s*2\.75rem;"
            ),
            "auth modal password toggle keeps a 44px square target": (
                r"\.token-toggle\s*\{[^}]*width:\s*2\.75rem;[^}]*height:\s*2\.75rem;"
            ),
        }
        missing = [
            label
            for label, pattern in required_patterns.items()
            if not re.search(pattern, css, re.S)
        ]
        if missing:
            fail(f"home page is missing thumb-friendly auth control markers: {', '.join(missing)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_toast_close_action_is_accessible():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-toast-a11y-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        css = page_css(html)
        if not re.search(
            r"\.toast__close\s*\{[^}]*width:\s*2\.75rem;[^}]*height:\s*2\.75rem;", css, re.S
        ):
            fail("home page should keep the toast close button at a 44px target size")
        if "toast_close" not in html:
            fail("home page should expose a localized toast close label in APP_UI")

        toast_js = (ROOT / "server" / "static" / "js" / "modules" / "toast.js").read_text(
            encoding="utf-8"
        )
        required_js_markers = [
            "closeBtn.className = 'toast__close';",
            "closeBtn.setAttribute('type', 'button');",
            "closeBtn.setAttribute('aria-label', uiText('toast_close', 'Dismiss notification'));",
        ]
        missing_js = [marker for marker in required_js_markers if marker not in toast_js]
        if missing_js:
            fail(
                f"toast manager is missing accessible close button markers: {', '.join(missing_js)}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_background_picker_keeps_thumb_friendly_tiles():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-bg-picker-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        css = page_css(html)
        if not re.search(
            r"\.user-panel-bg-grid\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(2\.75rem,\s*1fr\)\);",
            css,
            re.S,
        ):
            fail("home page should size background picker columns with a 44px minimum")
        if not re.search(
            r"\.bg-option\s*\{[^}]*min-width:\s*2\.75rem;[^}]*min-height:\s*2\.75rem;", css, re.S
        ):
            fail("home page should keep each background option at or above a 44px target size")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_toasts_expose_live_region_semantics():
    toast_js = (ROOT / "server" / "static" / "js" / "modules" / "toast.js").read_text(
        encoding="utf-8"
    )
    required_js_markers = [
        "this.container.setAttribute('aria-live', 'polite');",
        "this.container.setAttribute('aria-atomic', 'false');",
        "toast.setAttribute('role', type === 'error' ? 'alert' : 'status');",
    ]
    missing_js = [marker for marker in required_js_markers if marker not in toast_js]
    if missing_js:
        fail(f"toast manager is missing live region semantics: {', '.join(missing_js)}")


def scenario_home_auth_gate_opens_before_console_navigation():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-auth-gate-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        html = response.text
        required_html_markers = [
            'id="auth-modal"',
            'id="auth-form"',
            'data-auth-required="true"',
            'data-auth-target="/library?lang=zh"',
            'data-auth-target="/access?lang=zh"',
            'data-auth-target="/shares?lang=zh"',
            'data-auth-target="/activity?lang=zh"',
        ]
        missing_html = [marker for marker in required_html_markers if marker not in html]
        if missing_html:
            fail(
                f"home page is missing auth gate markers for console links: {', '.join(missing_html)}"
            )

        auth_js = (ROOT / "server" / "static" / "js" / "modules" / "auth-home.js").read_text(
            encoding="utf-8"
        )
        required_js_markers = [
            "const link = event.target.closest('[data-auth-required=\"true\"]');",
            "const targetHref = link.dataset.authTarget || link.getAttribute('href') || null;",
            "openAuthModal(targetHref);",
        ]
        missing_js = [marker for marker in required_js_markers if marker not in auth_js]
        if missing_js:
            fail(f"auth session runtime is missing auth gate markers: {', '.join(missing_js)}")
        if (
            'id="login-btn" type="submit"' not in html
            and 'type="submit" id="login-btn"' not in html
        ):
            fail("home page auth modal should expose a submit button for the auth form")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_user_entry_floats_clear_of_content_cards():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-user-trigger-layout-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        css = (ROOT / "server" / "static" / "css" / "input.css").read_text(encoding="utf-8")
        required_patterns = {
            "user trigger wrapper fixed to viewport": (
                r"\.user-trigger-wrapper\s*\{[^}]*position:\s*fixed;[^}]*right:\s*max\(1rem,\s*calc\(\(100vw\s*-\s*1200px\)\s*/\s*2\)\);"
            ),
            "user trigger stays below the top chrome on desktop": (
                r"\.user-trigger-wrapper\s*\{[^}]*top:\s*calc\(12px\s*\+\s*5\.5rem\);"
            ),
            "user panel still anchors to trigger": (
                r"\.user-panel\s*\{[^}]*position:\s*absolute;[^}]*top:\s*calc\(100%\s*\+\s*0\.75rem\);[^}]*right:\s*0;"
            ),
            "mobile user trigger docks away from content cards": (
                r"@media\s*\(max-width:\s*1023px\)\s*\{.*?\.user-trigger-wrapper\s*\{[^}]*top:\s*auto;[^}]*bottom:\s*calc\(4\.5rem\s*\+\s*env\(safe-area-inset-bottom,\s*0px\)\);"
            ),
            "mobile user panel opens upward from the docked trigger": (
                r"@media\s*\(max-width:\s*1023px\)\s*\{.*?\.user-panel\s*\{[^}]*top:\s*auto;[^}]*bottom:\s*calc\(100%\s*\+\s*0\.5rem\);"
            ),
        }
        missing = [
            label
            for label, pattern in required_patterns.items()
            if not re.search(pattern, css, re.S)
        ]
        if missing:
            fail(f"home page user entry still overlaps the content layout: {', '.join(missing)}")

        banned_patterns = {
            "user trigger wrapper in normal flow": r"\.user-trigger-wrapper\s*\{[^}]*position:\s*relative;",
        }
        present = [
            label for label, pattern in banned_patterns.items() if re.search(pattern, css, re.S)
        ]
        if present:
            fail(f"home page still contains in-flow user trigger rules: {', '.join(present)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_dark_mode_uses_dark_aware_surface_tokens():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-dark-surfaces-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/")
        if response.status_code != 200:
            fail(f"expected GET / to return 200, got {response.status_code}: {response.text}")

        css = page_css(response.text)
        required_snippets = [
            "--kawaii-panel:rgba(var(--kawaii-white-rgb),0.84);",
            "--kawaii-panel-soft:rgba(var(--kawaii-white-rgb),0.74);",
            "--kawaii-line:#dcc4d2;",
            "--kawaii-panel:rgba(var(--kawaii-panel-dark-rgb),0.92);",
            "background:var(--kawaii-panel)",
            "background:var(--kawaii-panel-soft)",
            "border:1px solid var(--kawaii-line)",
        ]
        missing = [snippet for snippet in required_snippets if snippet not in css]
        if missing:
            fail(f"home page is missing dark-aware surface tokens: {', '.join(missing)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_dark_mode_softens_card_highlights():
    css = (ROOT / "server" / "static" / "css" / "input.css").read_text(encoding="utf-8")
    pattern = (
        r'html\[data-color-scheme="dark"\]\s+\.kawaii-card::after\s*\{'
        r".*?rgba\(var\(--kawaii-white-rgb\),\s*0\.08\)"
    )
    if not re.search(pattern, css, re.S):
        fail("home page is missing dark card highlight override")


def scenario_static_app_js_is_served_without_legacy_theme_conflicts():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-static-js-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/static/js/app.js")
        if response.status_code != 200:
            fail(
                f"expected GET /static/js/app.js to return 200, got {response.status_code}: {response.text}"
            )

        theme_init_js = (ROOT / "server" / "static" / "js" / "theme-init.js").read_text(
            encoding="utf-8"
        )
        theme_module_js = (ROOT / "server" / "static" / "js" / "modules" / "theme.js").read_text(
            encoding="utf-8"
        )
        required_snippets = {
            "theme-init.js": [
                "var storageKey = 'kawaii-color-scheme';",
                "root.dataset.colorScheme = scheme;",
            ],
            "modules/theme.js": [
                "export class ThemeManager",
                "html.dataset.colorScheme = scheme;",
            ],
        }
        missing = [
            f"{path}: {snippet}"
            for path, snippets in required_snippets.items()
            for snippet in snippets
            if snippet not in (theme_init_js if path == "theme-init.js" else theme_module_js)
        ]
        if missing:
            fail(
                f"static theme scripts are missing kawaii theme integration markers: {', '.join(missing)}"
            )

        banned_snippets = [
            "localStorage.getItem('theme')",
            "html.removeAttribute('data-theme')",
            "html.setAttribute('data-theme', theme)",
        ]
        present = [
            snippet
            for snippet in banned_snippets
            if snippet in theme_init_js or snippet in theme_module_js
        ]
        if present:
            fail(f"static theme scripts still contain legacy theme mutations: {', '.join(present)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_static_app_js_binds_copy_triggers_and_avoids_dead_create_route():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-home-kawaii-copy-js-"))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / "artifacts")

        from fastapi.testclient import TestClient

        from server.app import create_app

        client = TestClient(create_app())
        response = client.get("/static/js/app.js")
        if response.status_code != 200:
            fail(
                f"expected GET /static/js/app.js to return 200, got {response.status_code}: {response.text}"
            )

        api_js = (ROOT / "server" / "static" / "js" / "modules" / "api.js").read_text(
            encoding="utf-8"
        )
        search_js = (ROOT / "server" / "static" / "js" / "modules" / "search.js").read_text(
            encoding="utf-8"
        )
        required_snippets = {
            "modules/api.js": [
                "querySelectorAll('[data-copy]')",
                "copyToClipboard(trigger.dataset.copy || '')",
            ],
            "modules/search.js": [
                "scripts/new-skill.sh publisher/my-skill basic",
            ],
        }
        missing = [
            f"{path}: {snippet}"
            for path, snippets in required_snippets.items()
            for snippet in snippets
            if snippet not in (api_js if path == "modules/api.js" else search_js)
        ]
        if missing:
            fail(
                f"static js modules are missing copy trigger hardening markers: {', '.join(missing)}"
            )

        banned_snippets = [
            "link.href = '/console/new-skill';",
        ]
        present = [
            snippet for snippet in banned_snippets if snippet in api_js or snippet in search_js
        ]
        if present:
            fail(
                f"static js modules still contain dead create-skill navigation: {', '.join(present)}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_static_app_js_is_valid_javascript():
    app_js_path = ROOT / "server" / "static" / "js" / "app.js"
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-app-js-check-"))
    try:
        mjs_path = tmpdir / "app.mjs"
        mjs_path.write_text(app_js_path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            result = subprocess.run(
                ["node", "--check", str(mjs_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            fail(f"node is required to verify app.js syntax: {exc}")

        if result.returncode != 0:
            fail(
                f"app.js should be valid javascript, got: {(result.stderr or result.stdout).strip()}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_home_uses_kawaii_theme_with_live_context()
    scenario_home_uses_refined_kawaii_presentation()
    scenario_home_supports_readable_copy_and_mobile_adaptation()
    scenario_home_polish_tightens_rhythm_and_clarifies_ctas()
    scenario_home_supports_manual_theme_and_language_switches()
    scenario_home_english_copy_stays_english_and_preserves_lang_routes()
    scenario_home_chinese_copy_stays_chinese_in_primary_chrome()
    scenario_home_chinese_auth_copy_uses_access_token_terms()
    scenario_home_mobile_touch_targets_stay_thumb_friendly()
    scenario_home_auth_controls_keep_thumb_friendly_targets()
    scenario_home_toast_close_action_is_accessible()
    scenario_home_background_picker_keeps_thumb_friendly_tiles()
    scenario_home_toasts_expose_live_region_semantics()
    scenario_home_auth_gate_opens_before_console_navigation()
    scenario_home_user_entry_floats_clear_of_content_cards()
    scenario_home_dark_mode_uses_dark_aware_surface_tokens()
    scenario_home_dark_mode_softens_card_highlights()
    scenario_static_app_js_is_served_without_legacy_theme_conflicts()
    scenario_static_app_js_binds_copy_triggers_and_avoids_dead_create_route()
    scenario_static_app_js_is_valid_javascript()
    print("OK: home kawaii theme checks passed")


if __name__ == "__main__":
    main()
