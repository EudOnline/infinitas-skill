#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.artifact_ops import sync_catalog_artifacts


def fail(message: str):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_ARTIFACT_PATH'] = str(tmpdir / 'artifacts')
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(
        [
            {
                'username': 'fixture-maintainer',
                'display_name': 'Fixture Maintainer',
                'role': 'maintainer',
                'token': 'fixture-maintainer-token',
            }
        ]
    )
    os.environ.pop('INFINITAS_REGISTRY_READ_TOKENS', None)


def scenario_home_uses_kawaii_theme_with_live_context():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-theme-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        checks = [
            ('kawaii theme root attribute', 'data-theme="kawaii"' in html),
            ('kawaii layout topbar present', 'class="topbar animate-in"' in html),
            ('kawaii layout topbar controls present', 'class="topbar-controls"' in html),
            ('kawaii layout shell present', 'class="site-shell"' in html),
            ('kawaii layout language toggles present', '/?lang=' in html),
            ('home anchor nav start', 'href="#start"' in html),
            ('home anchor nav handoff', 'href="#handoff"' in html),
            ('home anchor nav console', 'href="#console"' in html),
            ('no broken skills nav on home', 'href="/skills"' not in html),
            ('auth modal uses dialog semantics', 'role="dialog"' in html and 'aria-modal="true"' in html and 'aria-labelledby="auth-modal-title"' in html),
            ('user trigger exposes controlled panel', 'aria-controls="user-panel"' in html),
            ('status chip mode present', '🔒 模式' in html),
            ('status chip sync present', '📅 同步' in html),
            ('status chip queue present', '⚡ 队列' in html),
        ]
        if '/v2' in html:
            fail('home page should not reference /v2 after kawaii cutover')
        failures = [label for label, passed in checks if not passed]
        if failures:
            fail(f'home page did not satisfy kawaii homepage expectations: {", ".join(failures)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_uses_refined_kawaii_presentation():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-refined-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        banned_markers = [
            '-webkit-text-fill-color: transparent',
            '--ease-bounce',
            '--ease-elastic',
            "document.addEventListener('mousemove'",
            'createSparkle(',
            '@keyframes sparklePop',
        ]
        present = [marker for marker in banned_markers if marker in html]
        if present:
            fail(f'home page still contains unrefined presentation markers: {", ".join(present)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_supports_readable_copy_and_mobile_adaptation():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-mobile-readable-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_snippets = [
            '--kawaii-ink-soft: #64637d',
            '--kawaii-ink-muted: #7c7b92',
            'overflow-wrap: anywhere;',
            'min-width: 0;',
        ]
        missing_snippets = [snippet for snippet in required_snippets if snippet not in html]
        if missing_snippets:
            fail(f'home page is missing readability hardening markers: {", ".join(missing_snippets)}')

        mobile_patterns = {
            'hero CTA fills mobile width': r'@media \(max-width: 720px\).*?\.hero-cta\s*\{\s*width:\s*100%;',
            'section CTA fills mobile width': r'@media \(max-width: 720px\).*?\.section-action\s*\{\s*width:\s*100%;',
            'section button fills mobile width': r'@media \(max-width: 720px\).*?\.section-action\s+\.kawaii-button\s*\{\s*width:\s*100%;',
            'console and skill grids collapse to one column': r'@media \(max-width: 720px\).*?\.console-grid,\s*\.skills-grid\s*\{\s*grid-template-columns:\s*1fr;',
        }
        missing_patterns = [label for label, pattern in mobile_patterns.items() if not re.search(pattern, html, re.S)]
        if missing_patterns:
            fail(f'home page is missing mobile adaptation rules: {", ".join(missing_patterns)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_polish_tightens_rhythm_and_clarifies_ctas():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-polish-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        spacing_patterns = {
            'desktop hero spacing set': r'\.hero-section\s*\{\s*margin-bottom:\s*1rem;',
            'desktop status spacing set': r'\.status-section\s*\{\s*margin-bottom:\s*1rem;',
            'desktop console spacing set': r'\.console-section\s*\{\s*margin-bottom:\s*1rem;',
            'section topline spacing set': r'\.section-topline\s*\{.*?margin-bottom:\s*0\.75rem;',
        }
        missing_spacing = [label for label, pattern in spacing_patterns.items() if not re.search(pattern, html, re.S)]
        if missing_spacing:
            fail(f'home page is missing final rhythm polish markers: {", ".join(missing_spacing)}')

        required_copy = [
            '复制任务提示',
            '打开维护台',
            '复制检查命令',
            '快速开始',
            '常用技能',
        ]
        missing_copy = [label for label in required_copy if label not in html]
        if missing_copy:
            fail(f'home page is missing clearer CTA copy: {", ".join(missing_copy)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_supports_manual_theme_and_language_switches():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-switches-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        zh_response = client.get('/')
        en_response = client.get('/?lang=en')
        if zh_response.status_code != 200:
            fail(f'expected GET / to return 200, got {zh_response.status_code}: {zh_response.text}')
        if en_response.status_code != 200:
            fail(f'expected GET /?lang=en to return 200, got {en_response.status_code}: {en_response.text}')

        zh_html = zh_response.text
        en_html = en_response.text

        required_theme_markers = [
            'data-theme-choice="light"',
            'data-theme-choice="dark"',
            'kawaii-color-scheme',
            'html[data-color-scheme="dark"]',
        ]
        missing_theme = [marker for marker in required_theme_markers if marker not in zh_html]
        if missing_theme:
            fail(f'home page is missing manual theme controls: {", ".join(missing_theme)}')

        zh_markers = [
            '<html lang="zh-CN"',
            '浅色',
            '深色',
            '中',
            '>EN<',
        ]
        missing_zh = [marker for marker in zh_markers if marker not in zh_html]
        if missing_zh:
            fail(f'home page is missing chinese toggle labels: {", ".join(missing_zh)}')

        en_markers = [
            '<html lang="en"',
            'Copy task prompt',
            'Open console',
            'Light',
            'Dark',
            'Home base',
        ]
        missing_en = [marker for marker in en_markers if marker not in en_html]
        if missing_en:
            fail(f'home page is missing english rendering markers: {", ".join(missing_en)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_english_copy_stays_english_and_preserves_lang_routes():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-en-i18n-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/?lang=en')
        if response.status_code != 200:
            fail(f'expected GET /?lang=en to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_strings = [
            'Quick start',
            'Tap to copy and paste into your Agent chat',
            'Authentication',
            'Enter your access token to unlock personalized settings',
            'Enter your access token',
            'Token stays valid for 30 days',
            '>Cancel<',
            '>Verify<',
            'Copy inspect command',
            "name: 'Sakura Street'",
            "name: 'Starry Night'",
        ]
        missing_strings = [marker for marker in required_strings if marker not in html]
        if missing_strings:
            fail(f'english home page is missing localized ui copy: {", ".join(missing_strings)}')

        unexpected_chinese_bg_names = ['樱花街道', '动漫天空', '星空夜景', '赛博朋克']
        present_chinese_bg_names = [marker for marker in unexpected_chinese_bg_names if marker in html]
        if present_chinese_bg_names:
            fail(f'english home page should not embed chinese-only background preset names: {", ".join(present_chinese_bg_names)}')

        required_href_markers = [
            'href="/?lang=en"',
            'data-auth-target="/submissions?lang=en"',
            'data-auth-target="/reviews?lang=en"',
            'data-auth-target="/jobs?lang=en"',
        ]
        missing_hrefs = [marker for marker in required_href_markers if marker not in html]
        if missing_hrefs:
            fail(f'english home page is missing language-preserving navigation markers: {", ".join(missing_hrefs)}')

        search_markers = [
            'placeholder="Search skills or commands"',
            'aria-label="Search skills or commands"',
            'aria-label="Search results"',
        ]
        missing_search = [marker for marker in search_markers if marker not in html]
        if missing_search:
            fail(f'english home page is missing localized search accessibility markers: {", ".join(missing_search)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_auth_gate_opens_before_console_navigation():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-auth-gate-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_markers = [
            'id="auth-modal"',
            'data-auth-required="true"',
            'data-auth-target="/submissions?lang=zh"',
            'data-auth-target="/reviews?lang=zh"',
            'data-auth-target="/jobs?lang=zh"',
            'let pendingAuthTarget = null;',
            "openAuthModal(targetHref = null)",
            "document.querySelectorAll('[data-auth-required=\"true\"]').forEach",
        ]
        missing = [marker for marker in required_markers if marker not in html]
        if missing:
            fail(f'home page is missing auth gate markers for console links: {", ".join(missing)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_user_entry_stays_in_flow_without_fixed_overlap():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-user-trigger-layout-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_patterns = {
            'user trigger wrapper uses flow layout': (
                r'\.user-trigger-wrapper\s*\{[^}]*position:\s*relative;[^}]*display:\s*flex;[^}]*justify-content:\s*flex-end;'
            ),
            'user panel anchors to wrapper instead of viewport': (
                r'\.user-panel\s*\{[^}]*position:\s*absolute;[^}]*top:\s*calc\(100%\s*\+\s*0\.75rem\);[^}]*right:\s*0;'
            ),
        }
        missing = [label for label, pattern in required_patterns.items() if not re.search(pattern, html, re.S)]
        if missing:
            fail(f'home page still uses overlapping user overlay positioning: {", ".join(missing)}')

        banned_patterns = {
            'user trigger fixed to viewport': r'\.user-trigger-wrapper\s*\{[^}]*position:\s*fixed;',
            'user panel fixed to viewport': r'\.user-panel\s*\{[^}]*position:\s*fixed;',
        }
        present = [label for label, pattern in banned_patterns.items() if re.search(pattern, html, re.S)]
        if present:
            fail(f'home page still contains overlapping fixed user overlay rules: {", ".join(present)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_dark_mode_uses_dark_aware_surface_tokens():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-dark-surfaces-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_snippets = [
            '--kawaii-panel: rgba(255, 255, 255, 0.84);',
            '--kawaii-panel-soft: rgba(255, 255, 255, 0.74);',
            '--kawaii-line: rgba(220, 196, 210, 0.72);',
            '--kawaii-panel: rgba(35, 35, 60, 0.92);',
            'background: var(--kawaii-panel);',
            'background: var(--kawaii-panel-soft);',
            'border: 1px solid var(--kawaii-line);',
        ]
        missing = [snippet for snippet in required_snippets if snippet not in html]
        if missing:
            fail(f'home page is missing dark-aware surface tokens: {", ".join(missing)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_dark_mode_softens_card_highlights():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-card-highlight-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/')
        if response.status_code != 200:
            fail(f'expected GET / to return 200, got {response.status_code}: {response.text}')

        html = response.text
        required_patterns = {
            'explicit dark card highlight override': (
                r'html\[data-color-scheme="dark"\]\s+\.kawaii-card::after\s*\{'
                r'.*?rgba\(255,\s*255,\s*255,\s*0\.08\)'
            ),
            'system dark fallback card highlight override': (
                r'@media\s*\(prefers-color-scheme:\s*dark\)\s*\{'
                r'.*?html:not\(\[data-color-scheme\]\)\s+\.kawaii-card::after\s*\{'
                r'.*?rgba\(255,\s*255,\s*255,\s*0\.08\)'
            ),
        }
        missing = [label for label, pattern in required_patterns.items() if not re.search(pattern, html, re.S)]
        if missing:
            fail(f'home page is missing dark card highlight overrides: {", ".join(missing)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_static_app_js_is_served_without_legacy_theme_conflicts():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-static-js-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/static/js/app.js')
        if response.status_code != 200:
            fail(f'expected GET /static/js/app.js to return 200, got {response.status_code}: {response.text}')

        js = response.text
        required_snippets = [
            "const storageKey = 'kawaii-color-scheme';",
            'html.dataset.colorScheme = scheme;',
            "window.themeManager = new ThemeManager();",
        ]
        missing = [snippet for snippet in required_snippets if snippet not in js]
        if missing:
            fail(f'static app.js is missing kawaii theme integration markers: {", ".join(missing)}')

        banned_snippets = [
            "localStorage.getItem('theme')",
            "html.removeAttribute('data-theme')",
            "html.setAttribute('data-theme', theme)",
        ]
        present = [snippet for snippet in banned_snippets if snippet in js]
        if present:
            fail(f'static app.js still contains legacy theme mutations: {", ".join(present)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_static_app_js_binds_copy_triggers_and_avoids_dead_create_route():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-kawaii-copy-js-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        response = client.get('/static/js/app.js')
        if response.status_code != 200:
            fail(f'expected GET /static/js/app.js to return 200, got {response.status_code}: {response.text}')

        js = response.text
        required_snippets = [
            "querySelectorAll('[data-copy]')",
            'copyToClipboard(trigger.dataset.copy',
            'scripts/new-skill.sh lvxiaoer/my-skill basic',
        ]
        missing = [snippet for snippet in required_snippets if snippet not in js]
        if missing:
            fail(f'static app.js is missing copy trigger hardening markers: {", ".join(missing)}')

        banned_snippets = [
            "link.href = '/console/new-skill';",
        ]
        present = [snippet for snippet in banned_snippets if snippet in js]
        if present:
            fail(f'static app.js still contains dead create-skill navigation: {", ".join(present)}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_static_app_js_is_valid_javascript():
    try:
        result = subprocess.run(
            ['node', '--check', str(ROOT / 'server' / 'static' / 'js' / 'app.js')],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        fail(f'node is required to verify app.js syntax: {exc}')

    if result.returncode != 0:
        fail(f'app.js should be valid javascript, got: {(result.stderr or result.stdout).strip()}')


def main():
    scenario_home_uses_kawaii_theme_with_live_context()
    scenario_home_uses_refined_kawaii_presentation()
    scenario_home_supports_readable_copy_and_mobile_adaptation()
    scenario_home_polish_tightens_rhythm_and_clarifies_ctas()
    scenario_home_supports_manual_theme_and_language_switches()
    scenario_home_english_copy_stays_english_and_preserves_lang_routes()
    scenario_home_auth_gate_opens_before_console_navigation()
    scenario_home_user_entry_stays_in_flow_without_fixed_overlap()
    scenario_home_dark_mode_uses_dark_aware_surface_tokens()
    scenario_home_dark_mode_softens_card_highlights()
    scenario_static_app_js_is_served_without_legacy_theme_conflicts()
    scenario_static_app_js_binds_copy_triggers_and_avoids_dead_create_route()
    scenario_static_app_js_is_valid_javascript()
    print('OK: home kawaii theme checks passed')


if __name__ == '__main__':
    main()
