#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NAME = 'server-demo-skill'
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


def fixture_skill_files():
    meta = {
        'name': FIXTURE_NAME,
        'publisher': 'lvxiaoer',
        'qualified_name': f'lvxiaoer/{FIXTURE_NAME}',
        'version': FIXTURE_VERSION,
        'status': 'incubating',
        'summary': 'Hosted registry worker publish fixture',
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
            'description: Hosted registry worker publish fixture.\n'
            '---\n\n'
            '# Hosted Worker Fixture\n\n'
            'Used only by automated hosted worker tests.\n'
        ),
        '_meta.json': meta,
        'CHANGELOG.md': (
            '# Changelog\n\n'
            f'## {FIXTURE_VERSION} - 2026-03-13\n'
            '- Added hosted worker publish fixture.\n'
        ),
        'tests/smoke.md': '# Smoke\n\n- Confirm the worker fixture installs and publishes.\n',
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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-worker-publish-test-'))
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
    return tmpdir, repo, artifacts, key_path


def configure_env(tmpdir: Path, repo: Path, artifacts: Path, key_path: Path):
    os.environ['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{tmpdir / "server.db"}'
    os.environ['INFINITAS_SERVER_SECRET_KEY'] = 'test-secret-key'
    os.environ['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(make_bootstrap_users())
    os.environ['INFINITAS_SERVER_REPO_PATH'] = str(repo)
    os.environ['INFINITAS_SERVER_ARTIFACT_PATH'] = str(artifacts)
    os.environ['INFINITAS_SKILL_GIT_SIGNING_KEY'] = str(key_path)


def scenario_worker_publishes_submission_and_syncs_artifacts():
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
                'payload_summary': 'Fixture submission for worker publish tests',
                'payload': {
                    'files': fixture_skill_files(),
                },
            },
        )
        if create_response.status_code != 201:
            fail(f'create submission returned {create_response.status_code}: {create_response.text}')
        submission = create_response.json()
        submission_id = submission.get('id')
        if not submission_id:
            fail(f'missing submission id: {submission}')

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

        processed = run_worker_loop()
        if processed < 3:
            fail(f'expected worker to process at least 3 jobs, got {processed}')

        active_skill_dir = repo / 'skills' / 'active' / FIXTURE_NAME
        if not active_skill_dir.is_dir():
            fail(f'expected promoted active skill at {active_skill_dir}')

        manifest_path = artifacts / 'catalog' / 'distributions' / 'lvxiaoer' / FIXTURE_NAME / FIXTURE_VERSION / 'manifest.json'
        bundle_path = artifacts / 'catalog' / 'distributions' / 'lvxiaoer' / FIXTURE_NAME / FIXTURE_VERSION / 'skill.tar.gz'
        provenance_path = artifacts / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        for path in [manifest_path, bundle_path, provenance_path]:
            if not path.exists():
                fail(f'expected hosted artifact output at {path}')

        job_response = client.get(f'/api/v1/jobs/{publish_job_id}', headers=maintainer_headers)
        if job_response.status_code != 200:
            fail(f'job log lookup returned {job_response.status_code}: {job_response.text}')
        job_payload = job_response.json()
        log_text = job_payload.get('log') or ''
        if 'scripts/publish-skill.sh' not in log_text:
            fail(f'expected publish job log to include scripts/publish-skill.sh, got:\n{log_text}')

        validate_job_id = validate_job.json().get('job', {}).get('id')
        promote_job_id = promote_job.json().get('job', {}).get('id')
        validate_log = client.get(f'/api/v1/jobs/{validate_job_id}', headers=maintainer_headers).json().get('log') or ''
        promote_log = client.get(f'/api/v1/jobs/{promote_job_id}', headers=maintainer_headers).json().get('log') or ''
        if 'scripts/check-skill.sh' not in validate_log:
            fail(f'expected validation log to include scripts/check-skill.sh, got:\n{validate_log}')
        if 'scripts/promote-skill.sh' not in promote_log:
            fail(f'expected promotion log to include scripts/promote-skill.sh, got:\n{promote_log}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_worker_publishes_submission_and_syncs_artifacts()
    print('OK: worker publish checks passed')


if __name__ == '__main__':
    main()
