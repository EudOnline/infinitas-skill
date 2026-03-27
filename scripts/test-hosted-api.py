#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

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

        response = client.get('/healthz')
        if response.status_code != 200:
            fail(f'/healthz returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('ok') is not True:
            fail(f'/healthz returned unexpected payload: {payload}')

        response = client.get('/login')
        if response.status_code != 200:
            fail(f'/login returned {response.status_code}: {response.text}')

        response = client.get('/')
        if response.status_code != 200:
            fail(f'/ returned {response.status_code}: {response.text}')
        for href in ['/submissions', '/reviews', '/jobs']:
            if href not in response.text:
                fail(f'index page missing operator link {href!r}')
        for needle in [
            '交给 Agent',
            '搜索、检查和执行都交给它。',
            '交任务',
            '执行命令',
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
            ('/submissions', 'Submissions'),
            ('/reviews', 'Reviews'),
            ('/jobs', 'Jobs'),
        ]:
            response = client.get(route)
            if response.status_code != 401:
                fail(f'expected {route} without token to return 401, got {response.status_code}')
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
