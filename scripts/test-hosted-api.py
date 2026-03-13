#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def configure_env(tmpdir: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
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

        from fastapi.testclient import TestClient
        from server.app import app

        client = TestClient(app)

        response = client.get('/healthz')
        if response.status_code != 200:
            fail(f'/healthz returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('ok') is not True:
            fail(f'/healthz returned unexpected payload: {payload}')

        response = client.get('/login')
        if response.status_code != 200:
            fail(f'/login returned {response.status_code}: {response.text}')

        response = client.get(
            '/api/v1/me',
            headers={'Authorization': 'Bearer fixture-maintainer-token'},
        )
        if response.status_code != 200:
            fail(f'/api/v1/me returned {response.status_code}: {response.text}')
        payload = response.json()
        if payload.get('username') != 'fixture-maintainer':
            fail(f'unexpected username payload: {payload}')
        if payload.get('role') != 'maintainer':
            fail(f'unexpected role payload: {payload}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_health_login_and_me()
    print('OK: hosted api smoke checks passed')


if __name__ == '__main__':
    main()
