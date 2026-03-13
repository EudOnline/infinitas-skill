#!/usr/bin/env python3
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def prepare_db(tmpdir: Path) -> Path:
    db_path = tmpdir / 'worker.db'
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('create table if not exists bootstrap(ok integer)')
        conn.execute('insert into bootstrap(ok) values (1)')
        conn.commit()
    finally:
        conn.close()
    return db_path


def scenario_render_systemd_bundle():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-service-bundle-test-'))
    try:
        output_dir = tmpdir / 'rendered'
        repo_root = '/srv/infinitas/repo'
        env_file = '/etc/infinitas/hosted-registry.env'
        python_bin = '/opt/infinitas/.venv/bin/python'
        prefix = 'infinitas-hosted'

        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'render-hosted-systemd.py'),
                '--output-dir',
                str(output_dir),
                '--repo-root',
                repo_root,
                '--python-bin',
                python_bin,
                '--env-file',
                env_file,
                '--service-prefix',
                prefix,
                '--backup-output-dir',
                '/srv/infinitas/backups',
                '--backup-on-calendar',
                'daily',
                '--backup-label',
                'nightly',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')

        expected = {
            f'{prefix}.env.example',
            f'{prefix}-api.service',
            f'{prefix}-worker.service',
            f'{prefix}-backup.service',
            f'{prefix}-backup.timer',
        }
        found = {path.name for path in output_dir.iterdir()}
        missing = sorted(expected - found)
        if missing:
            fail(f'missing rendered files: {missing}')

        api_unit = (output_dir / f'{prefix}-api.service').read_text(encoding='utf-8')
        worker_unit = (output_dir / f'{prefix}-worker.service').read_text(encoding='utf-8')
        backup_service = (output_dir / f'{prefix}-backup.service').read_text(encoding='utf-8')
        backup_timer = (output_dir / f'{prefix}-backup.timer').read_text(encoding='utf-8')
        env_example = (output_dir / f'{prefix}.env.example').read_text(encoding='utf-8')

        assert_contains(api_unit, f'EnvironmentFile={env_file}', 'api unit')
        assert_contains(api_unit, python_bin, 'api unit')
        assert_contains(api_unit, 'uvicorn server.app:app', 'api unit')
        assert_contains(worker_unit, 'run-hosted-worker.py', 'worker unit')
        assert_contains(worker_unit, repo_root, 'worker unit')
        assert_contains(worker_unit, 'poll-interval', 'worker unit')
        assert_contains(backup_service, 'backup-hosted-registry.py', 'backup service')
        assert_contains(backup_service, '/srv/infinitas/backups', 'backup service')
        assert_contains(backup_timer, 'OnCalendar=daily', 'backup timer')
        assert_contains(env_example, 'INFINITAS_SERVER_DATABASE_URL=', 'env example')
        assert_contains(env_example, f'INFINITAS_SERVER_REPO_PATH={repo_root}', 'env example')

        deployment_doc = (ROOT / 'docs' / 'ops' / 'server-deployment.md').read_text(encoding='utf-8')
        backup_doc = (ROOT / 'docs' / 'ops' / 'server-backup-and-restore.md').read_text(encoding='utf-8')
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        assert_contains(deployment_doc, 'systemd', 'deployment doc')
        assert_contains(backup_doc, 'timer', 'backup doc')
        assert_contains(readme, 'render-hosted-systemd.py', 'README')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_worker_runner_once_smoke():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-worker-runner-test-'))
    try:
        db_path = prepare_db(tmpdir)
        artifact_dir = tmpdir / 'artifacts'
        artifact_dir.mkdir()
        repo_lock = tmpdir / 'repo.lock'
        env = os.environ.copy()
        env['INFINITAS_SERVER_DATABASE_URL'] = f'sqlite:///{db_path}'
        env['INFINITAS_SERVER_SECRET_KEY'] = 'fixture-secret'
        env['INFINITAS_SERVER_BOOTSTRAP_USERS'] = json.dumps(
            [{'username': 'fixture-maintainer', 'display_name': 'Fixture Maintainer', 'role': 'maintainer', 'token': 'fixture-token'}]
        )
        env['INFINITAS_SERVER_REPO_PATH'] = str(ROOT)
        env['INFINITAS_SERVER_ARTIFACT_PATH'] = str(artifact_dir)
        env['INFINITAS_SERVER_REPO_LOCK_PATH'] = str(repo_lock)

        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'run-hosted-worker.py'),
                '--once',
            ],
            cwd=ROOT,
            env=env,
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'processed', 'worker runner output')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_render_systemd_bundle()
    scenario_worker_runner_once_smoke()
    print('OK: hosted service bundle checks passed')


if __name__ == '__main__':
    main()
