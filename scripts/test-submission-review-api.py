#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(
        [
            {
                'username': 'fixture-contributor',
                'display_name': 'Fixture Contributor',
                'role': 'contributor',
                'token': 'fixture-contributor-token',
            },
            {
                'username': 'fixture-maintainer',
                'display_name': 'Fixture Maintainer',
                'role': 'maintainer',
                'token': 'fixture-maintainer-token',
            },
        ]
    )


def scenario_submission_review_flow_and_cli_help():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-submission-review-test-'))
    try:
        configure_env(tmpdir)

        from fastapi.testclient import TestClient
        from server.app import app

        contributor_headers = {'Authorization': 'Bearer fixture-contributor-token'}
        maintainer_headers = {'Authorization': 'Bearer fixture-maintainer-token'}

        client = TestClient(app)

        response = client.post(
            '/api/v1/submissions',
            headers=contributor_headers,
            json={
                'skill_name': 'server-demo-skill',
                'publisher': 'lvxiaoer',
                'payload_summary': 'Minimal hosted registry demo skill',
                'payload': {
                    'name': 'server-demo-skill',
                    'summary': 'Fixture payload for hosted API tests',
                    'entrypoint': 'SKILL.md',
                },
            },
        )
        if response.status_code != 201:
            fail(f'create submission returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('status') != 'draft':
            fail(f'expected draft status, got {payload}')
        submission_id = payload.get('id')
        if not submission_id:
            fail(f'missing submission id: {payload}')

        response = client.post(
            f'/api/v1/submissions/{submission_id}/request-validation',
            headers=contributor_headers,
            json={'note': 'Please validate the draft payload.'},
        )
        if response.status_code != 200:
            fail(f'request validation returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('status') != 'validation_requested':
            fail(f'expected validation_requested status, got {payload}')

        response = client.post(
            f'/api/v1/submissions/{submission_id}/request-review',
            headers=contributor_headers,
            json={'note': 'Ready for maintainer review.'},
        )
        if response.status_code != 200:
            fail(f'request review returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('status') != 'review_requested':
            fail(f'expected review_requested status, got {payload}')
        review = payload.get('review') or {}
        review_id = review.get('id')
        if not review_id:
            fail(f'missing review id: {payload}')

        response = client.post(
            f'/api/v1/reviews/{review_id}/approve',
            headers=contributor_headers,
            json={'note': 'Contributors should not be able to approve.'},
        )
        if response.status_code != 403:
            fail(f'expected contributor approval to be forbidden, got {response.status_code}: {response.text}')

        response = client.post(
            f'/api/v1/reviews/{review_id}/approve',
            headers=maintainer_headers,
            json={'note': 'Looks good to ship.'},
        )
        if response.status_code != 200:
            fail(f'maintainer approve returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('status') != 'approved':
            fail(f'expected approved status, got {payload}')

        response = client.get(f'/api/v1/submissions/{submission_id}', headers=contributor_headers)
        if response.status_code != 200:
            fail(f'fetch submission returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('status') != 'approved':
            fail(f'expected approved submission, got {payload}')
        history = payload.get('status_log') or []
        statuses = [entry.get('to') for entry in history]
        if statuses != ['draft', 'validation_requested', 'review_requested', 'approved']:
            fail(f'unexpected status log: {history}')

        cli = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'registryctl.py'), 'submissions', 'create', '--help'],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if cli.returncode != 0:
            fail(f'cli help exited {cli.returncode}\nstdout:\n{cli.stdout}\nstderr:\n{cli.stderr}')
        if '--skill-name' not in cli.stdout:
            fail(f'cli help missing expected flag output:\n{cli.stdout}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_submission_review_flow_and_cli_help()
    print('OK: submission review api checks passed')


if __name__ == '__main__':
    main()
