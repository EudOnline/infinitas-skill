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


def scenario_registry_requires_reader_token():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-hosted-registry-auth-test-'))
    try:
        configure_env(tmpdir)
        sync_catalog_artifacts(ROOT, tmpdir / 'artifacts')

        from fastapi.testclient import TestClient
        from server.app import create_app

        client = TestClient(create_app())

        response = client.get('/registry/ai-index.json')
        if response.status_code != 401:
            fail(f'expected unauthenticated registry request to return 401, got {response.status_code}')

        response = client.get(
            '/registry/ai-index.json',
            headers={'Authorization': 'Bearer wrong-token'},
        )
        if response.status_code != 401:
            fail(f'expected wrong registry token to return 401, got {response.status_code}')

        response = client.get(
            '/registry/ai-index.json',
            headers={'Authorization': 'Bearer registry-reader-token'},
        )
        if response.status_code != 200:
            fail(f'expected registry reader token to return 200, got {response.status_code}: {response.text}')

        response = client.get(
            '/registry/skills/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json',
            headers={'Authorization': 'Bearer registry-reader-token'},
        )
        if response.status_code != 200:
            fail(f'expected registry manifest request to return 200, got {response.status_code}: {response.text}')

        response = client.get(
            '/registry/catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json',
            headers={'Authorization': 'Bearer registry-reader-token'},
        )
        if response.status_code != 200:
            fail(
                'expected legacy registry catalog manifest request to return '
                f'200, got {response.status_code}: {response.text}'
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_registry_requires_reader_token()
    print('OK: hosted registry auth checks passed')


if __name__ == '__main__':
    main()
