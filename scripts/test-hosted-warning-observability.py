#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NAME = 'server-warning-skill'
FIXTURE_VERSION = '0.1.0'


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


def parse_json_or_fail(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f'{label} did not return JSON\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def fixture_skill_files():
    meta = {
        'name': FIXTURE_NAME,
        'publisher': 'lvxiaoer',
        'qualified_name': f'lvxiaoer/{FIXTURE_NAME}',
        'version': FIXTURE_VERSION,
        'status': 'incubating',
        'summary': 'Hosted warning observability fixture',
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
            f'name: {FIXTURE_NAME}\n'
            'description: Hosted warning observability fixture.\n'
            '---\n\n'
            '# Hosted Warning Fixture\n\n'
            'Used only by automated warning observability tests.\n'
        ),
        '_meta.json': meta,
        'CHANGELOG.md': (
            '# Changelog\n\n'
            f'## {FIXTURE_VERSION} - 2026-03-14\n'
            '- Added hosted warning observability fixture.\n'
        ),
        'tests/smoke.md': '# Smoke\n\n- Confirm warning observability fixture releases cleanly.\n',
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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-warning-observability-test-'))
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
    run(['git', 'config', 'user.name', 'Warning Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'warning@example.com'], cwd=repo)
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

    key_path = tmpdir / 'warning-key'
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'init-key',
            '--identity',
            'warning-hook',
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
            'warning-hook',
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
            'warning-hook',
            '--releaser',
            'Warning Fixture',
        ],
        cwd=repo,
    )
    run(['git', 'add', 'config/allowed_signers', 'policy/namespace-policy.json'], cwd=repo)
    run(['git', 'commit', '-m', 'bootstrap release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo, artifacts, key_path


def configure_env(tmpdir: Path, repo: Path, artifacts: Path, key_path: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(make_bootstrap_users())
    os.environ['INFINITAS_SERVER_REPO_PATH'] = str(repo)
    os.environ['INFINITAS_SERVER_ARTIFACT_PATH'] = str(artifacts)
    os.environ['INFINITAS_SKILL_GIT_SIGNING_KEY'] = str(key_path)
    os.environ['INFINITAS_SERVER_MIRROR_REMOTE'] = 'missing-remote'
    os.environ['INFINITAS_SERVER_MIRROR_BRANCH'] = 'main'


def queue_publish_flow(client, submission_id: int):
    contributor_headers = {'Authorization': 'Bearer fixture-contributor-token'}
    maintainer_headers = {'Authorization': 'Bearer fixture-maintainer-token'}

    if client.post(
        f'/api/v1/submissions/{submission_id}/request-validation',
        headers=contributor_headers,
        json={'note': 'Please validate'},
    ).status_code != 200:
        fail('request-validation route failed before worker queueing')

    review_response = client.post(
        f'/api/v1/submissions/{submission_id}/request-review',
        headers=contributor_headers,
        json={'note': 'Ready for maintainer review'},
    )
    if review_response.status_code != 200:
        fail(f'request-review returned {review_response.status_code}: {review_response.text}')
    review_id = ((review_response.json().get('review') or {}).get('id'))
    if not review_id:
        fail(f'missing review id: {review_response.json()}')

    approve_response = client.post(
        f'/api/v1/reviews/{review_id}/approve',
        headers=maintainer_headers,
        json={'note': 'Approve fixture submission for publish'},
    )
    if approve_response.status_code != 200:
        fail(f'approve returned {approve_response.status_code}: {approve_response.text}')

    validate_job = client.post(
        f'/api/v1/submissions/{submission_id}/queue-validation',
        headers=maintainer_headers,
        json={'note': 'Queue validation'},
    )
    if validate_job.status_code != 202:
        fail(f'queue-validation returned {validate_job.status_code}: {validate_job.text}')

    promote_job = client.post(
        f'/api/v1/submissions/{submission_id}/queue-promote',
        headers=maintainer_headers,
        json={'note': 'Queue promotion'},
    )
    if promote_job.status_code != 202:
        fail(f'queue-promote returned {promote_job.status_code}: {promote_job.text}')

    publish_job = client.post(
        f'/api/v1/skills/{FIXTURE_NAME}/publish',
        headers=maintainer_headers,
        json={'submission_id': submission_id},
    )
    if publish_job.status_code != 202:
        fail(f'publish queue returned {publish_job.status_code}: {publish_job.text}')
    publish_job_id = publish_job.json().get('job', {}).get('id')
    if not publish_job_id:
        fail(f'missing publish job id: {publish_job.json()}')
    return publish_job_id


def scenario_warning_jobs_surface_in_publish_and_inspect():
    tmpdir, repo, artifacts, key_path = prepare_repo()
    try:
        configure_env(tmpdir, repo, artifacts, key_path)

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
                'skill_name': FIXTURE_NAME,
                'publisher': 'lvxiaoer',
                'payload_summary': 'Fixture submission for warning observability tests',
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

        publish_job_id = queue_publish_flow(client, submission_id)
        processed = run_worker_loop()
        if processed < 3:
            fail(f'expected worker to process at least 3 jobs, got {processed}')

        manifest_path = artifacts / 'catalog' / 'distributions' / 'lvxiaoer' / FIXTURE_NAME / FIXTURE_VERSION / 'manifest.json'
        if not manifest_path.exists():
            fail(f'expected publish manifest at {manifest_path}')

        job_response = client.get(f'/api/v1/jobs/{publish_job_id}', headers=maintainer_headers)
        if job_response.status_code != 200:
            fail(f'job log lookup returned {job_response.status_code}: {job_response.text}')
        job_payload = job_response.json()
        if job_payload.get('status') != 'completed':
            fail(f'expected publish job to remain completed: {job_payload}')
        log_text = job_payload.get('log') or ''
        assert_contains(log_text, 'WARNING: publish mirror hook failed', 'publish job log')

        inspect_result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{tmpdir / "server.db"}',
                '--limit',
                '5',
                '--max-warning-jobs',
                '0',
                '--json',
            ],
            cwd=ROOT,
            expect=2,
        )
        payload = parse_json_or_fail(inspect_result, 'inspect warning payload')
        if payload.get('ok') is not False:
            fail(f'expected ok=false for warning alert payload: {payload}')
        jobs = payload.get('jobs') or {}
        if (jobs.get('warning_count') or 0) < 1:
            fail(f'expected warning_count >= 1: {payload}')
        warnings = jobs.get('recent_warnings') or []
        if not warnings:
            fail(f'expected recent_warnings entries: {payload}')
        if publish_job_id not in {item.get('id') for item in warnings}:
            fail(f'expected publish job in recent_warnings: {payload}')
        alert_kinds = {item.get('kind') for item in (payload.get('alerts') or [])}
        if 'warning_jobs' not in alert_kinds:
            fail(f'expected warning_jobs alert: {payload}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_warning_threshold():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-warning-inspect-render-'))
    try:
        output_dir = tmpdir / 'rendered'
        prefix = 'infinitas-hosted'
        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'render-hosted-systemd.py'),
                '--output-dir',
                str(output_dir),
                '--repo-root',
                '/srv/infinitas/repo',
                '--python-bin',
                '/opt/infinitas/.venv/bin/python',
                '--env-file',
                '/etc/infinitas/hosted-registry.env',
                '--service-prefix',
                prefix,
                '--backup-output-dir',
                '/srv/infinitas/backups',
                '--backup-on-calendar',
                'daily',
                '--backup-label',
                'nightly',
                '--inspect-on-calendar',
                'hourly',
                '--inspect-max-warning-jobs',
                '0',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')
        inspect_service_text = (output_dir / f'{prefix}-inspect.service').read_text(encoding='utf-8')
        assert_contains(inspect_service_text, '--max-warning-jobs 0', 'inspect service')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_warning_jobs_surface_in_publish_and_inspect()
    scenario_render_warning_threshold()
    print('OK: hosted warning observability checks passed')


if __name__ == '__main__':
    main()
