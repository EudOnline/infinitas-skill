#!/usr/bin/env python3
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.artifact_ops import sync_catalog_artifacts


def fail(message: str):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    env['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    env['INFINITAS_SERVER_ARTIFACT_PATH'] = str(tmpdir / 'artifacts')
    env['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(
        [
            {
                'username': 'fixture-maintainer',
                'display_name': 'Fixture Maintainer',
                'role': 'maintainer',
                'token': 'fixture-maintainer-token',
            }
        ]
    )
    env.pop('INFINITAS_REGISTRY_READ_TOKENS', None)
    return env


def configure_private_env(tmpdir: Path) -> dict[str, str]:
    env = configure_env(tmpdir)
    env['INFINITAS_REGISTRY_READ_TOKENS'] = json.dumps(['registry-reader-token'])
    return env


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class HostedAppServer:
    def __init__(self, repo: Path, env: dict[str, str]):
        self.repo = repo
        self.env = env
        self.process: subprocess.Popen[str] | None = None
        self.base_url: str | None = None

    def __enter__(self):
        port = reserve_port()
        self.base_url = f'http://127.0.0.1:{port}'
        self.process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'uvicorn',
                'server.app:app',
                '--host',
                '127.0.0.1',
                '--port',
                str(port),
            ],
            cwd=self.repo,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        health_url = self.base_url + '/healthz'
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.process.poll() is not None:
                output = self.process.stdout.read() if self.process.stdout else ''
                fail(f'hosted app exited before readiness\n{output}')
            try:
                with urllib.request.urlopen(health_url, timeout=1) as response:
                    if response.status == 200:
                        return self
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.2)
        fail(f'hosted app did not become ready at {health_url}')
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def playwright_cli_path() -> Path:
    codex_home = Path(os.environ.get('CODEX_HOME') or (Path.home() / '.codex'))
    candidate = codex_home / 'skills' / 'playwright' / 'scripts' / 'playwright_cli.sh'
    if not candidate.is_file():
        fail(f'expected Playwright CLI wrapper at {candidate}')
    return candidate


def run_playwright(session: str, *args: str, check: bool = True, timeout: float | None = 45) -> str:
    cmd = [str(playwright_cli_path()), *args, '--session', session]
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ''
        stderr = exc.stderr or ''
        if check:
            fail(
                'playwright command timed out:\n'
                f'command: {" ".join(cmd)}\n'
                f'stdout:\n{stdout}\n'
                f'stderr:\n{stderr}'
            )
        return stdout
    if check and result.returncode != 0:
        fail(
            'playwright command failed:\n'
            f'command: {" ".join(cmd)}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result.stdout


def run_playwright_global(*args: str, check: bool = True, timeout: float | None = 45) -> str:
    cmd = [str(playwright_cli_path()), *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ''
        stderr = exc.stderr or ''
        if check:
            fail(
                'playwright command timed out:\n'
                f'command: {" ".join(cmd)}\n'
                f'stdout:\n{stdout}\n'
                f'stderr:\n{stderr}'
            )
        return stdout
    if check and result.returncode != 0:
        fail(
            'playwright command failed:\n'
            f'command: {" ".join(cmd)}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result.stdout


def parse_eval_result(output: str) -> dict:
    marker = '### Result'
    marker_index = output.find(marker)
    if marker_index < 0:
        fail(f'expected Playwright eval output to contain {marker!r}, got:\n{output}')
    json_start = output.find('{', marker_index)
    json_end = output.rfind('}')
    if json_start < 0 or json_end < json_start:
        fail(f'expected JSON payload in Playwright eval output, got:\n{output}')
    try:
        return json.loads(output[json_start : json_end + 1])
    except json.JSONDecodeError as exc:
        fail(f'failed to parse Playwright eval payload: {exc}\n{output}')
    return {}


def wait_for_eval(session: str, script: str, predicate, description: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last_result = None
    while time.time() < deadline:
        last_result = parse_eval_result(run_playwright(session, 'eval', script))
        if predicate(last_result):
            return last_result
        time.sleep(0.2)
    fail(f'{description} did not converge before timeout; last result: {last_result}')
    return {}


def stop_playwright_session(session: str):
    run_playwright_global('session-stop', session, check=False, timeout=10)
    run_playwright_global('session-delete', session, check=False, timeout=10)


def scenario_home_waits_for_explicit_auth_before_probng_session():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-anon-runtime-'))
    session = f'homeanon{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            open_output = run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            if '/api/auth/me' in open_output or 'Unauthorized' in open_output:
                fail(f'expected anonymous home load to avoid auth/me probing, got:\n{open_output}')

            anonymous_state = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => ({'
                        'icon: document.getElementById("user-trigger-icon")?.textContent?.trim() || null,'
                        'loginHidden: document.getElementById("user-panel-login")?.hidden ?? null,'
                        'loggedHidden: document.getElementById("user-panel-logged")?.hidden ?? null,'
                        'cookieReady: document.cookie.includes("infinitas_auth_token=")'
                        '})'
                    ),
                )
            )
            if anonymous_state.get('cookieReady') is True:
                fail(f'expected anonymous home load to stay unauthenticated, got {anonymous_state}')
            if anonymous_state.get('icon') != '🔒':
                fail(f'expected anonymous home load to keep the locked icon, got {anonymous_state}')
            if anonymous_state.get('loginHidden') is not False or anonymous_state.get('loggedHidden') is not True:
                fail(f'expected anonymous home load to keep the login panel visible, got {anonymous_state}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_cookie_backed_session_survives_missing_local_storage():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-auth-runtime-'))
    session = f'homeauth{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/login?lang=en')
            parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'document.getElementById("token-input").value = "fixture-maintainer-token";'
                        'document.getElementById("login-btn").click();'
                        'return { submitted: true };'
                        '}'
                    ),
                )
            )
            wait_for_eval(
                session,
                (
                    '() => ({'
                    'path: location.pathname,'
                    'cookieReady: document.cookie.includes("infinitas_auth_token=")'
                    '})'
                ),
                lambda result: result.get('path') == '/' and result.get('cookieReady') is True,
                'login redirect to home with auth cookie',
            )

            cleared = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'localStorage.removeItem("infinitas_auth_token");'
                        'localStorage.removeItem("infinitas_auth_expiry");'
                        'return {'
                        'cookieReady: document.cookie.includes("infinitas_auth_token="),'
                        'token: localStorage.getItem("infinitas_auth_token"),'
                        'expiry: localStorage.getItem("infinitas_auth_expiry")'
                        '};'
                        '}'
                    ),
                )
            )
            if cleared.get('cookieReady') is not True:
                fail(f'expected auth cookie to remain after clearing localStorage, got {cleared}')
            if cleared.get('token') is not None or cleared.get('expiry') is not None:
                fail(f'expected localStorage auth keys to be cleared, got {cleared}')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            session_state = wait_for_eval(
                session,
                (
                    '() => ({'
                    'icon: document.getElementById("user-trigger-icon")?.textContent?.trim() || null,'
                    'loginHidden: document.getElementById("user-panel-login")?.hidden ?? null,'
                    'loggedHidden: document.getElementById("user-panel-logged")?.hidden ?? null,'
                    'cookieReady: document.cookie.includes("infinitas_auth_token=")'
                    '})'
                ),
                lambda result: (
                    result.get('cookieReady') is True
                    and result.get('icon') == '👤'
                    and result.get('loginHidden') is True
                    and result.get('loggedHidden') is False
                ),
                'cookie-only home auth state',
            )
            if session_state.get('icon') != '👤':
                fail(f'expected home page to show logged-in icon after cookie-only reload, got {session_state}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_stale_auth_cookie_clears_without_console_errors():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-stale-cookie-runtime-'))
    session = f'homestale{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'document.cookie = "infinitas_auth_token=stale-token; path=/; SameSite=Lax";'
                        'localStorage.setItem("infinitas_auth_token", "stale-token");'
                        'localStorage.setItem("infinitas_auth_expiry", String(Date.now() + 86400000));'
                        'return { ready: true };'
                        '}'
                    ),
                )
            )

            reload_output = run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            if 'Unauthorized' in reload_output or '/api/auth/me' in reload_output:
                fail(f'expected stale cookie probe to avoid unauthorized console noise, got:\n{reload_output}')

            stale_state = wait_for_eval(
                session,
                (
                    '() => ({'
                    'cookieReady: document.cookie.includes("infinitas_auth_token="),'
                    'localToken: localStorage.getItem("infinitas_auth_token"),'
                    'localExpiry: localStorage.getItem("infinitas_auth_expiry"),'
                    'icon: document.getElementById("user-trigger-icon")?.textContent?.trim() || null'
                    '})'
                ),
                lambda result: (
                    result.get('cookieReady') is False
                    and result.get('localToken') is None
                    and result.get('localExpiry') is None
                    and result.get('icon') == '🔒'
                ),
                'stale auth state cleared after probe',
            )
            if stale_state.get('icon') != '🔒':
                fail(f'expected stale auth state to end anonymous, got {stale_state}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_copy_triggers_work_and_search_empty_state_uses_copy_cta():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-copy-runtime-'))
    session = f'homecopy{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'window.__copied = null;'
                        'Object.defineProperty(navigator, "clipboard", {'
                        '  configurable: true,'
                        '  value: {'
                        '    writeText: async (value) => {'
                        '      window.__copied = value;'
                        '    }'
                        '  }'
                        '});'
                        'return { ready: true };'
                        '}'
                    ),
                )
            )

            copy_result = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'const trigger = document.querySelector(".hero-cta[data-copy]");'
                        'if (!trigger) return { error: "missing hero copy trigger" };'
                        'const expected = trigger.dataset.copy || null;'
                        'trigger.click();'
                        'return { expected, copied: window.__copied || null };'
                        '}'
                    ),
                )
            )
            if copy_result.get('error'):
                fail(copy_result['error'])
            if copy_result.get('copied') != copy_result.get('expected'):
                fail(f'expected hero copy trigger to write its payload, got {copy_result}')

            empty_state = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        '() => {'
                        'window.__copied = null;'
                        'window.searchManager.render({ skills: [], commands: [] });'
                        'window.searchManager.open();'
                        'const trigger = document.querySelector("#search-dropdown [data-copy]");'
                        'if (!trigger) {'
                        '  const link = document.querySelector("#search-dropdown a, #search-dropdown button");'
                        '  return {'
                        '    error: "missing empty-state copy CTA",'
                        '    tagName: link ? link.tagName : null,'
                        '    href: link ? link.getAttribute("href") : null'
                        '  };'
                        '}'
                        'const expected = trigger.dataset.copy || null;'
                        'trigger.click();'
                        'return {'
                        '  tagName: trigger.tagName,'
                        '  href: trigger.getAttribute("href"),'
                        '  expected,'
                        '  copied: window.__copied || null'
                        '};'
                        '}'
                    ),
                )
            )
            if empty_state.get('error'):
                fail(f'search empty state should expose a copy CTA, got {empty_state}')
            if empty_state.get('tagName') != 'BUTTON':
                fail(f'search empty state CTA should be a button instead of a dead link, got {empty_state}')
            if empty_state.get('href') is not None:
                fail(f'search empty state CTA should not navigate to another route, got {empty_state}')
            if empty_state.get('copied') != empty_state.get('expected'):
                fail(f'search empty state CTA should copy its starter command, got {empty_state}')

            search_skill = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        'async () => {'
                        'const input = document.getElementById("global-search");'
                        'if (!input || !window.searchManager) return { error: "missing search controls" };'
                        'input.value = "skill";'
                        'input.dispatchEvent(new Event("input", { bubbles: true }));'
                        'await new Promise((resolve) => setTimeout(resolve, 500));'
                        'const trigger = document.querySelector("#search-dropdown .search-result");'
                        'if (!trigger) return { error: "missing search skill result" };'
                        'return {'
                        '  tagName: trigger.tagName,'
                        '  href: trigger.getAttribute("href"),'
                        '  copy: trigger.dataset.copy || null'
                        '};'
                        '}'
                    ),
                )
            )
            if search_skill.get('error'):
                fail(search_skill['error'])
            if search_skill.get('tagName') != 'BUTTON':
                fail(f'search skill result should be a button action instead of a dead link, got {search_skill}')
            if search_skill.get('href') is not None:
                fail(f'search skill result should not navigate to a missing route, got {search_skill}')
            if not (search_skill.get('copy') or '').startswith('scripts/inspect-skill.sh '):
                fail(f'search skill result should expose an inspect command copy action, got {search_skill}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_english_auth_errors_stay_english():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-auth-i18n-runtime-'))
    session = f'homei18n{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            english_error = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        'async () => {'
                        'document.getElementById("open-auth-modal-btn").click();'
                        'document.getElementById("token-input").value = "badtoken";'
                        'document.getElementById("login-btn").click();'
                        'await new Promise((resolve) => setTimeout(resolve, 300));'
                        'return {'
                        '  error: document.getElementById("error-message")?.textContent?.trim() || null,'
                        '  hidden: document.getElementById("auth-error")?.hidden ?? null'
                        '};'
                        '}'
                    ),
                )
            )
            if english_error.get('hidden') is not False:
                fail(f'expected invalid english auth attempt to show an error, got {english_error}')
            if english_error.get('error') != 'Invalid token':
                fail(f'expected english auth error copy, got {english_error}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_home_english_runtime_ui_copy_stays_english():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-auth-runtime-copy-'))
    session = f'homecopy{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            english_runtime_copy = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        'async () => {'
                        'const trigger = document.getElementById("user-trigger");'
                        'trigger.click();'
                        'const openAuthBtn = document.getElementById("open-auth-modal-btn");'
                        'openAuthBtn.click();'
                        'const toggle = document.getElementById("token-toggle");'
                        'toggle.click();'
                        'document.getElementById("cancel-auth-btn").click();'
                        'await new Promise((resolve) => setTimeout(resolve, 50));'
                        'trigger.click();'
                        'openAuthBtn.click();'
                        'document.getElementById("token-input").value = "";'
                        'document.getElementById("login-btn").click();'
                        'await new Promise((resolve) => setTimeout(resolve, 50));'
                        'return {'
                        '  triggerAria: trigger.getAttribute("aria-label"),'
                        '  toggleAria: toggle.getAttribute("aria-label"),'
                        '  error: document.getElementById("error-message")?.textContent?.trim() || null'
                        '};'
                        '}'
                    ),
                )
            )
            if english_runtime_copy.get('triggerAria') != 'Sign in':
                fail(f'expected english home trigger aria-label to stay english, got {english_runtime_copy}')
            if english_runtime_copy.get('toggleAria') != 'Hide password':
                fail(f'expected english password toggle label to stay english, got {english_runtime_copy}')
            if english_runtime_copy.get('error') != 'Please enter token':
                fail(f'expected english local validation copy, got {english_runtime_copy}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_auth_modal_restores_focus_after_close():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-auth-focus-runtime-'))
    session = f'homefocus{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            focus_state = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        'async () => {'
                        'document.getElementById("user-trigger").click();'
                        'const trigger = document.getElementById("open-auth-modal-btn");'
                        'trigger.focus();'
                        'trigger.click();'
                        'document.getElementById("cancel-auth-btn").click();'
                        'await new Promise((resolve) => setTimeout(resolve, 50));'
                        'return {'
                        '  activeId: document.activeElement?.id || null,'
                        '  modalHidden: document.getElementById("auth-modal")?.hidden ?? null'
                        '};'
                        '}'
                    ),
                )
            )
            if focus_state.get('modalHidden') is not True:
                fail(f'expected auth modal to close, got {focus_state}')
            if focus_state.get('activeId') != 'user-trigger':
                fail(f'expected focus to return to auth trigger after close, got {focus_state}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_legacy_registry_reader_env_does_not_gate_home_search():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-legacy-reader-env-'))
    session = f'homelegacy{os.getpid()}'
    try:
        env = configure_private_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            public_search = wait_for_eval(
                session,
                (
                    'async () => {'
                    'const input = document.getElementById("global-search");'
                    'input.value = "install";'
                    'input.dispatchEvent(new Event("input", { bubbles: true }));'
                    'await new Promise((resolve) => setTimeout(resolve, 500));'
                    'const trigger = document.querySelector("#search-dropdown .search-result");'
                    'return {'
                    '  modalHidden: document.getElementById("auth-modal")?.hidden ?? null,'
                    '  bodyOverflow: document.body.style.overflow || "",'
                    '  dropdownHidden: document.getElementById("search-dropdown")?.hidden ?? null,'
                    '  resultTag: trigger?.tagName || null,'
                    '  resultCopy: trigger?.dataset.copy || null'
                    '};'
                    '}'
                ),
                lambda result: result.get('dropdownHidden') is False and result.get('resultTag') == 'BUTTON',
                'legacy registry reader env should not gate home search',
            )
            if public_search.get('modalHidden') is False:
                fail(f'expected legacy registry reader env to stop triggering auth prompts on home search, got {public_search}')
            if public_search.get('bodyOverflow'):
                fail(f'expected home search to keep body scroll unlocked, got {public_search}')
            if not (public_search.get('resultCopy') or '').startswith('scripts/inspect-skill.sh '):
                fail(f'expected legacy registry reader env to preserve home inspect actions, got {public_search}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_protected_console_route_redirects_into_auth_modal():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-home-protected-route-'))
    session = f'homeprotect{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/skills?lang=en')
            protected_redirect = wait_for_eval(
                session,
                (
                    '() => ({'
                    'path: location.pathname,'
                    'search: location.search,'
                    'modalHidden: document.getElementById("auth-modal")?.hidden ?? null,'
                    'tokenInput: !!document.getElementById("token-input"),'
                    'pageTitle: document.querySelector(".hero-title")?.textContent?.trim() || null'
                    '})'
                ),
                lambda result: result.get('path') == '/' and result.get('modalHidden') is False,
                'protected console redirect into auth modal',
            )
            if protected_redirect.get('tokenInput') is not True:
                fail(f'expected protected route redirect to expose the home auth modal, got {protected_redirect}')
            if protected_redirect.get('search') not in ('', '?lang=en'):
                fail(f'expected protected route redirect to clean up auth query params after boot, got {protected_redirect}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_console_search_reauth_uses_shared_modal():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-console-shared-auth-runtime-'))
    session = f'consoleauth{os.getpid()}'
    try:
        env = configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        stop_playwright_session(session)

        with HostedAppServer(ROOT, env) as server:
            if not server.base_url:
                fail('hosted app did not expose a base URL')

            run_playwright(session, 'open', f'{server.base_url}/?lang=en')
            login_state = parse_eval_result(
                run_playwright(
                    session,
                    'eval',
                    (
                        'async () => {'
                        'const res = await fetch("/api/auth/login?lang=en", {'
                        '  method: "POST",'
                        '  headers: { "Content-Type": "application/json" },'
                        '  body: JSON.stringify({ token: "fixture-maintainer-token" })'
                        '});'
                        'const data = await res.json();'
                        'return { ok: res.ok, success: data.success === true, username: data.username || null };'
                        '}'
                    ),
                )
            )
            if login_state.get('ok') is not True or login_state.get('success') is not True:
                fail(f'expected browser login bootstrap to succeed before console audit, got {login_state}')

            run_playwright(session, 'open', f'{server.base_url}/skills?lang=en')
            reauth_state = wait_for_eval(
                session,
                (
                    'async () => {'
                    'document.cookie = "infinitas_auth_token=; Max-Age=0; path=/; SameSite=Lax";'
                    'localStorage.removeItem("infinitas_auth_token");'
                    'localStorage.removeItem("infinitas_auth_expiry");'
                    'const input = document.getElementById("global-search");'
                    'if (!input) return { error: "missing console search input" };'
                    'input.value = "install";'
                    'input.dispatchEvent(new Event("input", { bubbles: true }));'
                    'await new Promise((resolve) => setTimeout(resolve, 500));'
                    'return {'
                    '  modalHidden: document.getElementById("console-auth-modal")?.hidden ?? null,'
                    '  hasTokenInput: !!document.getElementById("console-token-input"),'
                    '  bodyOverflow: document.body.style.overflow || "",'
                    '  dropdownHidden: document.getElementById("search-dropdown")?.hidden ?? null'
                    '};'
                    '}'
                ),
                lambda result: result.get('modalHidden') is False,
                'console search reauth shared modal',
            )
            if reauth_state.get('error'):
                fail(reauth_state['error'])
            if reauth_state.get('hasTokenInput') is not True:
                fail(f'expected console reauth flow to expose the shared auth modal input, got {reauth_state}')
            if reauth_state.get('bodyOverflow') != 'hidden':
                fail(f'expected console reauth modal to lock body scroll, got {reauth_state}')
    finally:
        stop_playwright_session(session)
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_home_waits_for_explicit_auth_before_probng_session()
    scenario_cookie_backed_session_survives_missing_local_storage()
    scenario_stale_auth_cookie_clears_without_console_errors()
    scenario_copy_triggers_work_and_search_empty_state_uses_copy_cta()
    scenario_english_auth_errors_stay_english()
    scenario_home_english_runtime_ui_copy_stays_english()
    scenario_auth_modal_restores_focus_after_close()
    scenario_legacy_registry_reader_env_does_not_gate_home_search()
    scenario_protected_console_route_redirects_into_auth_modal()
    scenario_console_search_reauth_uses_shared_modal()
    print('OK: home auth runtime checks passed')


if __name__ == '__main__':
    main()
