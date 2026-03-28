#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.artifact_ops import sync_catalog_artifacts


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_ARTIFACT_PATH'] = str(tmpdir / 'artifacts')
    os.environ['INFINITAS_REGISTRY_READ_TOKENS'] = json.dumps(['registry-reader-token'])
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


def scenario_health_login_and_me():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-hosted-api-test-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        maintainer_headers = {'Authorization': 'Bearer fixture-maintainer-token'}

        submission_response = client.post(
            '/api/v1/submissions',
            headers=maintainer_headers,
            json={
                'skill_name': 'ui-audit-skill',
                'publisher': 'lvxiaoer',
                'payload_summary': 'UI audit helper',
                'payload': {
                    'name': 'ui-audit-skill',
                    'summary': 'UI audit helper',
                },
            },
        )
        if submission_response.status_code != 201:
            fail(f'failed to seed submission fixture: {submission_response.status_code}: {submission_response.text}')
        submission_payload = submission_response.json()
        submission_id = submission_payload['id']

        review_request_response = client.post(
            f'/api/v1/submissions/{submission_id}/request-review',
            headers=maintainer_headers,
            json={'note': 'Queue for review'},
        )
        if review_request_response.status_code != 200:
            fail(
                'failed to move seeded submission into review_requested: '
                f'{review_request_response.status_code}: {review_request_response.text}'
            )
        review_requested_payload = review_request_response.json()

        queue_validation_response = client.post(
            f'/api/v1/submissions/{submission_id}/queue-validation',
            headers=maintainer_headers,
            json={'note': 'Run validation'},
        )
        if queue_validation_response.status_code != 202:
            fail(
                'failed to queue seeded validation job: '
                f'{queue_validation_response.status_code}: {queue_validation_response.text}'
            )
        queued_job_payload = queue_validation_response.json().get('job') or {}

        response = client.get('/healthz')
        if response.status_code != 200:
            fail(f'/healthz returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('ok') is not True:
            fail(f'/healthz returned unexpected payload: {payload}')

        response = client.get('/login')
        if response.status_code != 200:
            fail(f'/login returned {response.status_code}: {response.text}')
        zh_login_html = response.text
        zh_login_markers = [
            '令牌认证',
            '输入访问令牌',
            '输入你的访问令牌',
            '访问令牌可在个人账户设置中获取',
            '访问令牌无效',
            '请输入访问令牌',
            '访问令牌长度不能少于 8 位',
            '访问令牌长度不能超过 128 位',
            'window.location.href = \'/?lang=zh\'',
            'href="/?lang=zh"',
            "/api/auth/login?lang=zh",
        ]
        missing_zh_login = [marker for marker in zh_login_markers if marker not in zh_login_html]
        if missing_zh_login:
            fail(f'chinese login page is missing localized auth markers: {", ".join(missing_zh_login)}')
        unexpected_zh_login = [
            'Token 可在个人账户设置中获取',
            'Token 无效',
            '请输入 Token',
            'Token 长度不能少于 8 位',
            'Token 长度不能超过 128 位',
        ]
        present_zh_login = [marker for marker in unexpected_zh_login if marker in zh_login_html]
        if present_zh_login:
            fail(
                'chinese login page should avoid mixed Token wording, found: '
                + ', '.join(present_zh_login)
            )

        response = client.get('/login?lang=en')
        if response.status_code != 200:
            fail(f'/login?lang=en returned {response.status_code}: {response.text}')
        english_login_html = response.text
        english_login_markers = [
            'Token Auth',
            'Enter Access Token',
            'Enter your access token',
            'window.location.href = \'/?lang=en\'',
            'href="/?lang=en"',
            "/api/auth/login?lang=en",
        ]
        missing_english_login = [marker for marker in english_login_markers if marker not in english_login_html]
        if missing_english_login:
            fail(f'english login page is missing localized auth markers: {", ".join(missing_english_login)}')
        duplicate_console_auth_markers = [
            'id="console-session-trigger"',
            'id="console-session-panel"',
            'id="console-auth-modal"',
        ]
        unexpected_console_auth_markers = [
            marker for marker in duplicate_console_auth_markers if marker in english_login_html
        ]
        if unexpected_console_auth_markers:
            fail(
                'expected /login to avoid rendering duplicate shared console auth controls, found: '
                + ', '.join(unexpected_console_auth_markers)
            )

        response = client.post('/api/auth/login?lang=en', json={'token': 'badtoken'})
        if response.status_code != 200:
            fail(f'/api/auth/login?lang=en returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('error') != 'Invalid token':
            fail(f'expected english invalid token error, got {payload}')

        response = client.get('/api/auth/me')
        if response.status_code != 200:
            fail(f'/api/auth/me without session should return 200, got {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('authenticated') is not False:
            fail(f'expected anonymous /api/auth/me probe to report authenticated=false, got {payload}')

        response = client.get('/')
        if response.status_code != 200:
            fail(f'/ returned {response.status_code}: {response.text}')
        for href in ['/submissions', '/reviews', '/jobs']:
            if href not in response.text:
                fail(f'index page missing operator link {href!r}')
        for needle in [
            '交给 Agent',
            '搜索、检查和执行都交给它。',
            '复制任务提示',
            '快速开始',
            '同步',
            '有事再进维护台',
        ]:
            if needle not in response.text:
                fail(f'index page missing agent-first homepage content {needle!r}')

        response = client.get(
            '/api/v1/me',
            headers=maintainer_headers,
        )
        if response.status_code != 200:
            fail(f'/api/v1/me returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('username') != 'fixture-maintainer':
            fail(f'unexpected username payload: {payload}')
        if payload.get('role') != 'maintainer':
            fail(f'unexpected role payload: {payload}')

        response = client.get('/api/search?q=install&lang=en', headers={'Authorization': 'Bearer registry-reader-token'})
        if response.status_code != 200:
            fail(f'/api/search?q=install&lang=en returned {response.status_code}: {response.text}')
        payload = response.json()
        english_command_names = [item.get('name') for item in payload.get('commands', [])]
        if 'Install skill' not in english_command_names:
            fail(f'expected english search commands for lang=en, got {english_command_names}')

        response = client.get('/registry/ai-index.json')
        if response.status_code != 401:
            fail(f'expected /registry/ai-index.json without token to return 401, got {response.status_code}')

        response = client.get(
            '/registry/ai-index.json',
            headers={'Authorization': 'Bearer fixture-maintainer-token'},
        )
        if response.status_code != 401:
            fail(
                'expected /registry/ai-index.json with hosted user token to return '
                f'401, got {response.status_code}'
            )

        for route in [
            '/registry/ai-index.json',
            '/registry/distributions.json',
            '/registry/compatibility.json',
            '/registry/skills/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json',
        ]:
            response = client.get(
                route,
                headers={'Authorization': 'Bearer registry-reader-token'},
            )
            if response.status_code != 200:
                fail(f'{route} returned {response.status_code}: {response.text}')

        for route, heading in [
            ('/submissions', '提交队列'),
            ('/reviews', '评审台'),
            ('/jobs', '任务台'),
        ]:
            response = client.get(route, follow_redirects=False)
            if response.status_code not in (302, 303, 307, 308):
                fail(f'expected {route} without token to redirect into the auth flow, got {response.status_code}')
            location = response.headers.get('location', '')
            if not location.startswith('/?lang=zh&auth=required&next='):
                fail(f'expected {route} redirect to land on the home auth flow, got {location!r}')
            response = client.get(route, headers=maintainer_headers)
            if response.status_code != 200:
                fail(f'expected {route} with maintainer token to return 200, got {response.status_code}: {response.text}')
            if heading not in response.text:
                fail(f'expected {route} page to contain heading {heading!r}')
            for marker in ['data-theme="kawaii"', 'data-theme-choice="light"', 'data-theme-choice="dark"']:
                if marker not in response.text:
                    fail(f'expected {route} page to include kawaii theme marker {marker!r}')
            theme_label_candidates = ['aria-label="Theme switcher"', 'aria-label="主题切换"']
            if not any(label in response.text for label in theme_label_candidates):
                fail(f'expected {route} page to expose the theme toggle group')
            language_label_candidates = ['aria-label="Language switcher"', 'aria-label="语言切换"']
            if not any(label in response.text for label in language_label_candidates):
                fail(f'expected {route} page to expose the language toggle group')
            for shell_marker in [
                'class="topbar animate-in"',
                'class="topbar-controls"',
                'class="site-shell"',
            ]:
                if shell_marker not in response.text:
                    fail(f'expected {route} page to include kawaii shell marker {shell_marker!r}')

        for route in ['/submissions?lang=en', '/reviews?lang=en', '/jobs?lang=en']:
            response = client.get(route, follow_redirects=False)
            if response.status_code not in (302, 303, 307, 308):
                fail(f'expected {route} without a session to redirect into the auth flow, got {response.status_code}')
            location = response.headers.get('location')
            if not location:
                fail(f'expected {route} redirect to include a location header')
            parts = urlsplit(location)
            params = dict(parse_qsl(parts.query, keep_blank_values=True))
            if parts.path != '/':
                fail(f'expected {route} redirect to land on /, got {location!r}')
            if params.get('lang') != 'en':
                fail(f'expected {route} redirect to preserve lang=en, got {location!r}')
            if params.get('auth') != 'required':
                fail(f'expected {route} redirect to request auth, got {location!r}')
            if params.get('next') != route:
                fail(f'expected {route} redirect to preserve the protected target, got {location!r}')

        for route, heading in [
            ('/submissions?lang=en', 'Submissions queue'),
            ('/reviews?lang=en', 'Reviews desk'),
            ('/jobs?lang=en', 'Jobs desk'),
        ]:
            response = client.get(route, headers=maintainer_headers)
            if response.status_code != 200:
                fail(f'expected {route} with maintainer token to return 200, got {response.status_code}: {response.text}')
            if heading not in response.text:
                fail(f'expected {route} page to contain english heading {heading!r}')
            english_nav_markers = [
                'href="/?lang=en"',
                'href="/submissions?lang=en"',
                'href="/reviews?lang=en"',
                'href="/jobs?lang=en"',
                'aria-label="Theme switcher"',
                'aria-label="Language switcher"',
            ]
            missing_english_nav = [marker for marker in english_nav_markers if marker not in response.text]
            if missing_english_nav:
                fail(f'expected {route} page to preserve english navigation markers: {", ".join(missing_english_nav)}')

        session_client = TestClient(create_app())
        response = session_client.post('/api/auth/login', json={'token': 'fixture-maintainer-token'})
        if response.status_code != 200:
            fail(f'/api/auth/login returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('success') is not True:
            fail(f'/api/auth/login should accept valid token, got {payload}')
        set_cookie = response.headers.get('set-cookie', '')
        if 'infinitas_auth_token=' not in set_cookie:
            fail(f'/api/auth/login should set auth cookie, got headers {dict(response.headers)}')

        response = session_client.get('/submissions')
        if response.status_code != 200:
            fail(
                'expected /submissions to accept the authenticated browser session after login, '
                f'got {response.status_code}: {response.text}'
            )
        if '提交队列' not in response.text:
            fail('expected /submissions session-auth response to render the console page')

        response = session_client.get('/submissions?lang=en')
        if response.status_code != 200:
            fail(
                'expected /submissions?lang=en to accept the authenticated browser session after login, '
                f'got {response.status_code}: {response.text}'
            )
        english_submissions_html = response.text
        english_console_auth_markers = [
            'id="console-session-trigger"',
            'id="console-session-panel"',
            'id="console-open-auth-modal-btn"',
            'id="console-logout-btn"',
            'id="console-auth-modal"',
            'window.openAuthModal = openAuthModal;',
        ]
        missing_console_auth_markers = [
            marker for marker in english_console_auth_markers if marker not in english_submissions_html
        ]
        if missing_console_auth_markers:
            fail(
                'expected english submissions console to expose shared auth controls, missing: '
                + ', '.join(missing_console_auth_markers)
            )
        if 'Waiting review' not in english_submissions_html:
            fail('expected submissions console to humanize review_requested into Waiting review')
        if '>review_requested<' in english_submissions_html:
            fail('submissions console should not leak raw review_requested status text into the UI')
        raw_submission_updated_at = review_requested_payload.get('updated_at')
        if raw_submission_updated_at and raw_submission_updated_at in english_submissions_html:
            fail(
                'submissions console should format timestamps for humans instead of rendering raw ISO values, '
                f'but still found {raw_submission_updated_at!r}'
            )

        response = session_client.get('/jobs?lang=en')
        if response.status_code != 200:
            fail(
                'expected /jobs?lang=en to accept the authenticated browser session after login, '
                f'got {response.status_code}: {response.text}'
            )
        english_jobs_html = response.text
        if 'Validate submission' not in english_jobs_html:
            fail('expected jobs console to humanize validate_submission into Validate submission')
        if '>validate_submission<' in english_jobs_html:
            fail('jobs console should not leak raw validate_submission job kinds into the UI')
        raw_job_updated_at = queued_job_payload.get('updated_at')
        if raw_job_updated_at and raw_job_updated_at in english_jobs_html:
            fail(
                'jobs console should format timestamps for humans instead of rendering raw ISO values, '
                f'but still found {raw_job_updated_at!r}'
            )

        response = session_client.get('/api/search?q=install&lang=en')
        if response.status_code != 200:
            fail(
                'expected /api/search to accept the authenticated browser session in private mode, '
                f'got {response.status_code}: {response.text}'
            )
        payload = response.json()
        english_session_command_names = [item.get('name') for item in payload.get('commands', [])]
        if 'Install skill' not in english_session_command_names:
            fail(f'expected session-auth search to stay localized in english, got {english_session_command_names}')

        response = session_client.get('/api/skills/consume-infinitas-skill')
        if response.status_code != 200:
            fail(
                'expected /api/skills/{id} to accept the authenticated browser session in private mode, '
                f'got {response.status_code}: {response.text}'
            )
        payload = response.json()
        if payload.get('name') != 'consume-infinitas-skill':
            fail(f'expected session-auth skill detail payload, got {payload}')

        response = client.get('/v2', follow_redirects=False)
        if response.status_code not in (307, 308):
            fail(f'/v2 should redirect to / with 307/308, got {response.status_code}')
        location = response.headers.get('location')
        if location != '/':
            fail(f'/v2 redirect location should be /, got {location!r}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_health_login_and_me()
    print('OK: hosted api smoke checks passed')


if __name__ == '__main__':
    main()
