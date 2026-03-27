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


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(
        [
            {
                'username': 'fixture-contributor-a',
                'display_name': 'Fixture Contributor A',
                'role': 'contributor',
                'token': 'fixture-contributor-a-token',
            },
            {
                'username': 'fixture-contributor-b',
                'display_name': 'Fixture Contributor B',
                'role': 'contributor',
                'token': 'fixture-contributor-b-token',
            },
            {
                'username': 'fixture-maintainer',
                'display_name': 'Fixture Maintainer',
                'role': 'maintainer',
                'token': 'fixture-maintainer-token',
            },
        ]
    )


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class HostedAppServer:
    def __init__(self, repo: Path, env: dict[str, str]):
        self.repo = repo
        self.env = env
        self.process = None
        self.base_url = None

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


def create_submission(client, token: str, skill_name: str):
    response = client.post(
        '/api/v1/submissions',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'skill_name': skill_name,
            'publisher': 'lvxiaoer',
            'payload_summary': f'{skill_name} summary',
            'payload': {
                'name': skill_name,
                'summary': f'{skill_name} payload',
            },
        },
    )
    if response.status_code != 201:
        fail(f'create submission for {skill_name} returned {response.status_code}: {response.text}')
    return response.json()


def post_transition(client, path: str, token: str, note: str, expect: int):
    response = client.post(
        path,
        headers={'Authorization': f'Bearer {token}'},
        json={'note': note},
    )
    if response.status_code != expect:
        fail(f'{path} returned {response.status_code}, expected {expect}: {response.text}')
    return response.json()


def seed_operator_data(client):
    submission_a = create_submission(client, 'fixture-contributor-a-token', 'operator-skill-a')
    submission_b = create_submission(client, 'fixture-contributor-b-token', 'operator-skill-b')

    review_a = post_transition(
        client,
        f"/api/v1/submissions/{submission_a['id']}/request-review",
        'fixture-contributor-a-token',
        'Please review A.',
        200,
    )['review']
    review_b = post_transition(
        client,
        f"/api/v1/submissions/{submission_b['id']}/request-review",
        'fixture-contributor-b-token',
        'Please review B.',
        200,
    )['review']

    post_transition(
        client,
        f"/api/v1/reviews/{review_a['id']}/approve",
        'fixture-maintainer-token',
        'Approved A.',
        200,
    )
    post_transition(
        client,
        f"/api/v1/submissions/{submission_a['id']}/queue-validation",
        'fixture-maintainer-token',
        'Queue validation A.',
        202,
    )
    post_transition(
        client,
        f"/api/v1/submissions/{submission_b['id']}/queue-validation",
        'fixture-maintainer-token',
        'Queue validation B.',
        202,
    )

    return {
        'submission_a_id': submission_a['id'],
        'submission_b_id': submission_b['id'],
        'review_a_id': review_a['id'],
        'review_b_id': review_b['id'],
    }


def assert_submission_list(payload, expected_ids: list[int]):
    if payload.get('total') != len(expected_ids):
        fail(f"expected submission total {len(expected_ids)}, got {payload.get('total')}: {payload}")
    items = payload.get('items') or []
    ids = [item.get('id') for item in items]
    if ids != expected_ids:
        fail(f'expected submission ids {expected_ids}, got {ids}: {payload}')
    for item in items:
        for field in ['id', 'skill_name', 'publisher', 'status', 'created_at', 'updated_at']:
            if not item.get(field):
                fail(f'missing submission field {field!r}: {item}')


def assert_review_list(payload, expected_ids: list[int]):
    if payload.get('total') != len(expected_ids):
        fail(f"expected review total {len(expected_ids)}, got {payload.get('total')}: {payload}")
    items = payload.get('items') or []
    ids = [item.get('id') for item in items]
    if ids != expected_ids:
        fail(f'expected review ids {expected_ids}, got {ids}: {payload}')
    for item in items:
        for field in ['id', 'submission_id', 'status', 'created_at', 'updated_at']:
            if item.get(field) in (None, ''):
                fail(f'missing review field {field!r}: {item}')


def assert_job_list(payload, expected_submission_ids: list[int]):
    if payload.get('total') != len(expected_submission_ids):
        fail(f"expected job total {len(expected_submission_ids)}, got {payload.get('total')}: {payload}")
    items = payload.get('items') or []
    submission_ids = [item.get('submission_id') for item in items]
    if submission_ids != expected_submission_ids:
        fail(f'expected job submission ids {expected_submission_ids}, got {submission_ids}: {payload}')
    for item in items:
        for field in ['id', 'kind', 'status', 'submission_id', 'created_at', 'updated_at']:
            if item.get(field) in (None, ''):
                fail(f'missing job field {field!r}: {item}')


def run_cli(base_url: str, token: str, *args: str):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'registryctl.py'),
            '--base-url',
            base_url,
            '--token',
            token,
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(
            f'cli command {args!r} exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f'cli command {args!r} returned invalid json: {exc}\n{result.stdout}')


def scenario_operator_lists_and_cli():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-operator-console-test-'))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())
        seeded = seed_operator_data(client)

        response = client.get(
            '/api/v1/submissions',
            headers={'Authorization': 'Bearer fixture-maintainer-token'},
        )
        if response.status_code != 200:
            fail(f'maintainer submissions list returned {response.status_code}: {response.text}')
        assert_submission_list(response.json(), [seeded['submission_a_id'], seeded['submission_b_id']])

        response = client.get(
            '/api/v1/submissions',
            headers={'Authorization': 'Bearer fixture-contributor-a-token'},
        )
        if response.status_code != 200:
            fail(f'contributor submissions list returned {response.status_code}: {response.text}')
        assert_submission_list(response.json(), [seeded['submission_a_id']])

        response = client.get(
            '/api/v1/reviews',
            headers={'Authorization': 'Bearer fixture-maintainer-token'},
        )
        if response.status_code != 200:
            fail(f'maintainer reviews list returned {response.status_code}: {response.text}')
        assert_review_list(response.json(), [seeded['review_a_id'], seeded['review_b_id']])

        response = client.get(
            '/api/v1/reviews',
            headers={'Authorization': 'Bearer fixture-contributor-a-token'},
        )
        if response.status_code != 200:
            fail(f'contributor reviews list returned {response.status_code}: {response.text}')
        assert_review_list(response.json(), [seeded['review_a_id']])

        response = client.get(
            '/api/v1/jobs',
            headers={'Authorization': 'Bearer fixture-maintainer-token'},
        )
        if response.status_code != 200:
            fail(f'maintainer jobs list returned {response.status_code}: {response.text}')
        assert_job_list(response.json(), [seeded['submission_b_id'], seeded['submission_a_id']])

        response = client.get(
            '/api/v1/jobs',
            headers={'Authorization': 'Bearer fixture-contributor-a-token'},
        )
        if response.status_code != 200:
            fail(f'contributor jobs list returned {response.status_code}: {response.text}')
        assert_job_list(response.json(), [seeded['submission_a_id']])

        for route, heading, needle in [
            ('/submissions', 'Submissions', 'operator-skill-a'),
            ('/reviews', 'Reviews', 'Approved A.'),
            ('/jobs', 'Jobs', 'Queue validation A.'),
        ]:
            response = client.get(route)
            if response.status_code != 401:
                fail(f'expected {route} without token to return 401, got {response.status_code}')
            response = client.get(
                route,
                headers={'Authorization': 'Bearer fixture-contributor-a-token'},
            )
            if response.status_code != 403:
                fail(f'expected {route} with contributor token to return 403, got {response.status_code}')
            response = client.get(
                route,
                headers={'Authorization': 'Bearer fixture-maintainer-token'},
            )
            if response.status_code != 200:
                fail(f'expected {route} with maintainer token to return 200, got {response.status_code}: {response.text}')
            if heading not in response.text or needle not in response.text:
                fail(f'expected {route} page to contain {heading!r} and {needle!r}, got:\n{response.text}')
            for shared_needle in ['Maintainer-only console', 'registryctl.py']:
                if shared_needle not in response.text:
                    fail(f'expected {route} page to contain {shared_needle!r}, got:\n{response.text}')
            for theme_marker in ['data-theme=\"kawaii\"', 'data-theme-choice=\"light\"', 'data-theme-choice=\"dark\"']:
                if theme_marker not in response.text:
                    fail(f'expected {route} page to feature kawaii theme marker {theme_marker!r}')
            theme_label_candidates = ['aria-label=\"Theme switcher\"', 'aria-label=\"主题切换\"']
            if not any(label in response.text for label in theme_label_candidates):
                fail(f'expected {route} page to expose the theme toggle group')
            language_label_candidates = ['aria-label=\"Language switcher\"', 'aria-label=\"语言切换\"']
            if not any(label in response.text for label in language_label_candidates):
                fail(f'expected {route} page to expose the language toggle group')
            for shell_marker in [
                'class=\"topbar animate-in\"',
                'class=\"topbar-controls\"',
                'class=\"site-shell\"',
            ]:
                if shell_marker not in response.text:
                    fail(f'expected {route} page to include kawaii shell marker {shell_marker!r}, got:\n{response.text}')
        for route, needle in [
            ('/reviews', 'Decision hints'),
            ('/reviews', 'Approve quickly'),
            ('/jobs', 'Queue health'),
            ('/jobs', 'Worker rhythm'),
        ]:
            response = client.get(
                route,
                headers={'Authorization': 'Bearer fixture-maintainer-token'},
            )
            if needle not in response.text:
                fail(f'expected {route} page to contain {needle!r}, got:\n{response.text}')

        response = client.get('/v2', follow_redirects=False)
        if response.status_code not in (307, 308):
            fail(f'/v2 should redirect to / with 307/308, got {response.status_code}')
        location = response.headers.get('location')
        if location != '/':
            fail(f'/v2 redirect location should be /, got {location!r}')

        with HostedAppServer(ROOT, os.environ.copy()) as server:
            payload = run_cli(server.base_url, 'fixture-maintainer-token', 'submissions', 'list')
            assert_submission_list(payload, [seeded['submission_a_id'], seeded['submission_b_id']])

            payload = run_cli(server.base_url, 'fixture-maintainer-token', 'reviews', 'list')
            assert_review_list(payload, [seeded['review_a_id'], seeded['review_b_id']])

            payload = run_cli(server.base_url, 'fixture-maintainer-token', 'jobs', 'list')
            assert_job_list(payload, [seeded['submission_b_id'], seeded['submission_a_id']])
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_operator_lists_and_cli()
    print('OK: hosted operator console checks passed')


if __name__ == '__main__':
    main()
