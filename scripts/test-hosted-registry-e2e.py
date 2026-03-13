#!/usr/bin/env python3
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = 'hosted-e2e-skill'
VERSION = '0.2.0'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fixture_skill_files():
    meta = {
        'name': SKILL_NAME,
        'publisher': 'lvxiaoer',
        'qualified_name': f'lvxiaoer/{SKILL_NAME}',
        'version': VERSION,
        'status': 'incubating',
        'summary': 'Hosted registry end-to-end fixture',
        'risk_level': 'low',
        'owner': 'release-owner',
        'owners': ['release-owner'],
        'maintainers': ['release-owner'],
        'author': 'release-owner',
        'review_state': 'approved',
        'distribution': {
            'installable': True,
            'channel': 'git',
        },
    }
    return {
        'SKILL.md': (
            '---\n'
            f'name: {SKILL_NAME}\n'
            'description: Hosted registry end-to-end fixture.\n'
            '---\n\n'
            '# Hosted Registry E2E Fixture\n\n'
            'Used only by the hosted registry end-to-end test.\n'
        ),
        '_meta.json': meta,
        'CHANGELOG.md': (
            '# Changelog\n\n'
            f'## {VERSION} - 2026-03-13\n'
            '- Added hosted registry end-to-end fixture.\n'
        ),
        'tests/smoke.md': '# Smoke\n\n- Confirm hosted end-to-end publish and install.\n',
        'VERSION.txt': VERSION + '\n',
    }


def make_bootstrap_users():
    return [
        {
            'username': 'release-owner',
            'display_name': 'Release Owner',
            'role': 'contributor',
            'token': 'fixture-contributor-token',
        },
        {
            'username': 'lvxiaoer',
            'display_name': 'Lvxiaoer',
            'role': 'maintainer',
            'token': 'fixture-maintainer-token',
        },
    ]


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-hosted-e2e-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    artifacts = tmpdir / 'artifacts'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            '.git',
            '.worktrees',
            '.planning',
            '__pycache__',
            '.cache',
            'scripts/__pycache__',
            '.state',
            'infinitas_hosted_registry.egg-info',
        ),
    )
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Release Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'release@example.com'], cwd=repo)
    run(['git', 'remote', 'add', 'origin', str(origin)], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    run(['git', 'push', '-u', 'origin', 'main'], cwd=repo)

    namespace_policy_path = repo / 'policy' / 'namespace-policy.json'
    namespace_policy = json.loads(namespace_policy_path.read_text(encoding='utf-8'))
    publisher = ((namespace_policy.get('publishers') or {}).get('lvxiaoer') or {})
    owners = publisher.get('owners') if isinstance(publisher.get('owners'), list) else []
    maintainers = publisher.get('maintainers') if isinstance(publisher.get('maintainers'), list) else []
    publisher['owners'] = list(dict.fromkeys([*owners, 'release-owner']))
    publisher['maintainers'] = list(dict.fromkeys([*maintainers, 'release-owner']))
    namespace_policy.setdefault('publishers', {})['lvxiaoer'] = publisher
    write_json(namespace_policy_path, namespace_policy)
    run(['git', 'add', 'policy/namespace-policy.json'], cwd=repo)
    run(['git', 'commit', '-m', 'authorize release owner for fixture publisher'], cwd=repo)
    run(['git', 'push'], cwd=repo)

    key_path = tmpdir / 'release-test-key'
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'init-key',
            '--identity',
            'release-test',
            '--output',
            str(key_path),
        ],
        cwd=repo,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'add-allowed-signer',
            '--identity',
            'release-test',
            '--key',
            str(key_path),
        ],
        cwd=repo,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'configure-git',
            '--key',
            str(key_path),
        ],
        cwd=repo,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'authorize-publisher',
            '--publisher',
            'lvxiaoer',
            '--signer',
            'release-test',
            '--releaser',
            'Release Fixture',
        ],
        cwd=repo,
    )
    run(['git', 'add', 'config/allowed_signers', 'policy/namespace-policy.json'], cwd=repo)
    run(['git', 'commit', '-m', 'bootstrap release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo, artifacts


def configure_env(tmpdir: Path, repo: Path, artifacts: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(make_bootstrap_users())
    os.environ['INFINITAS_SERVER_REPO_PATH'] = str(repo)
    os.environ['INFINITAS_SERVER_ARTIFACT_PATH'] = str(artifacts)


def configure_hosted_registry(repo: Path, base_url: str):
    registry_path = repo / 'config' / 'registry-sources.json'
    payload = json.loads(registry_path.read_text(encoding='utf-8'))
    payload['default_registry'] = 'hosted-e2e'
    for entry in payload.get('registries', []):
        if entry.get('name') == 'self':
            entry['enabled'] = False
    payload.setdefault('registries', []).append(
        {
            'name': 'hosted-e2e',
            'kind': 'http',
            'base_url': base_url,
            'enabled': True,
            'priority': 200,
            'trust': 'untrusted',
            'auth': {'mode': 'none'},
            'update_policy': {'mode': 'manual'},
            'notes': 'Hosted e2e registry fixture',
        }
    )
    write_json(registry_path, payload)


class QuietTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class HostedArtifactServer:
    def __init__(self, directory: Path):
        self.directory = directory
        self.httpd = None
        self.thread = None
        self.base_url = None

    def __enter__(self):
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(self.directory))
        self.httpd = QuietTCPServer(('127.0.0.1', 0), handler)
        port = self.httpd.server_address[1]
        self.base_url = f'http://127.0.0.1:{port}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)


def assert_install_success(repo: Path, runtime_dir: Path, base_url: str):
    result = run([str(repo / 'scripts' / 'install-by-name.sh'), SKILL_NAME, str(runtime_dir)], cwd=repo)
    payload = json.loads(result.stdout)
    if payload.get('state') != 'installed':
        fail(f"expected installed state, got {payload.get('state')!r}")
    manifest_path = Path(payload.get('manifest_path') or '')
    if not manifest_path.exists():
        fail(f'missing install manifest {manifest_path}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entry = ((manifest.get('skills') or {}).get(SKILL_NAME) or {})
    if entry.get('version') != VERSION:
        fail(f"expected installed version {VERSION}, got {entry.get('version')!r}")
    if entry.get('source_registry') != 'hosted-e2e':
        fail(f"expected source_registry 'hosted-e2e', got {entry.get('source_registry')!r}")
    if entry.get('source_registry_kind') != 'http':
        fail(f"expected source_registry_kind 'http', got {entry.get('source_registry_kind')!r}")
    if not isinstance(entry.get('source_repo'), str) or not entry['source_repo'].startswith(base_url):
        fail(f"expected hosted source_repo starting with {base_url!r}, got {entry.get('source_repo')!r}")
    version_txt = (runtime_dir / SKILL_NAME / 'VERSION.txt').read_text(encoding='utf-8').strip()
    if version_txt != VERSION:
        fail(f"expected installed VERSION.txt {VERSION!r}, got {version_txt!r}")


def scenario_hosted_registry_end_to_end():
    tmpdir, repo, artifacts = prepare_repo()
    try:
        configure_env(tmpdir, repo, artifacts)

        from fastapi.testclient import TestClient
        from server.app import create_app
        from server.worker import run_worker_loop

        app = create_app()
        client = TestClient(app)
        contributor_headers = {'Authorization': 'Bearer fixture-contributor-token'}
        maintainer_headers = {'Authorization': 'Bearer fixture-maintainer-token'}

        create_response = client.post(
            '/api/v1/submissions',
            headers=contributor_headers,
            json={
                'skill_name': SKILL_NAME,
                'publisher': 'lvxiaoer',
                'payload_summary': 'Hosted registry e2e fixture',
                'payload': {
                    'files': fixture_skill_files(),
                },
            },
        )
        if create_response.status_code != 201:
            fail(f'create submission returned {create_response.status_code}: {create_response.text}')
        submission_id = create_response.json().get('id')
        if not submission_id:
            fail(f'missing submission id: {create_response.json()}')

        if client.post(
            f'/api/v1/submissions/{submission_id}/request-validation',
            headers=contributor_headers,
            json={'note': 'Validate e2e fixture'},
        ).status_code != 200:
            fail('request-validation failed in e2e flow')

        review_response = client.post(
            f'/api/v1/submissions/{submission_id}/request-review',
            headers=contributor_headers,
            json={'note': 'Review e2e fixture'},
        )
        if review_response.status_code != 200:
            fail(f'request-review returned {review_response.status_code}: {review_response.text}')
        review_id = ((review_response.json().get('review') or {}).get('id'))
        if not review_id:
            fail(f'missing review id: {review_response.json()}')

        approve_response = client.post(
            f'/api/v1/reviews/{review_id}/approve',
            headers=maintainer_headers,
            json={'note': 'Approve e2e fixture'},
        )
        if approve_response.status_code != 200:
            fail(f'approve returned {approve_response.status_code}: {approve_response.text}')

        for path in [
            f'/api/v1/submissions/{submission_id}/queue-validation',
            f'/api/v1/submissions/{submission_id}/queue-promote',
        ]:
            response = client.post(path, headers=maintainer_headers, json={'note': 'Queue e2e worker step'})
            if response.status_code != 202:
                fail(f'queue step {path} returned {response.status_code}: {response.text}')

        publish_response = client.post(
            f'/api/v1/skills/{SKILL_NAME}/publish',
            headers=maintainer_headers,
            json={'submission_id': submission_id, 'note': 'Queue e2e publish'},
        )
        if publish_response.status_code != 202:
            fail(f'publish queue returned {publish_response.status_code}: {publish_response.text}')

        processed = run_worker_loop()
        if processed < 3:
            fail(f'expected worker to process at least 3 jobs, got {processed}')

        provenance_path = artifacts / 'catalog' / 'provenance' / f'{SKILL_NAME}-{VERSION}.json'
        if not provenance_path.exists():
            fail(f'missing provenance file {provenance_path}')

        doctor = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'doctor-signing.py'),
                SKILL_NAME,
                '--identity',
                'release-test',
                '--provenance',
                str(provenance_path),
                '--json',
            ],
            cwd=repo,
        )
        doctor_payload = json.loads(doctor.stdout)
        if doctor_payload.get('overall_status') != 'ok':
            fail(f"expected doctor overall_status 'ok', got {doctor_payload.get('overall_status')!r}")

        with HostedArtifactServer(artifacts) as server:
            configure_hosted_registry(repo, server.base_url)
            runtime_dir = tmpdir / 'runtime-skills'
            assert_install_success(repo, runtime_dir, server.base_url)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_hosted_registry_end_to_end()
    print('OK: hosted registry e2e checks passed')


if __name__ == '__main__':
    main()
