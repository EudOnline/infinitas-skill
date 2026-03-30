#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from test_support.server_ops import (
    HealthServer,
    prepare_artifacts,
    prepare_repo,
    prepare_sqlite_db,
    run_command as shared_run_command,
)


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0, env=None):
    try:
        return shared_run_command(command, cwd=cwd, expect=expect, env=env)
    except SystemExit as exc:
        fail(str(exc).removeprefix('FAIL: '))


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def scenario_healthcheck_and_backup_success():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-ops-test-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)
        backup_root = tmpdir / 'backups'
        backup_root.mkdir()

        with HealthServer() as base_url:
            health = run(
                [
                    sys.executable,
                    str(ROOT / 'scripts' / 'server-healthcheck.py'),
                    '--api-url',
                    base_url,
                    '--repo-path',
                    str(repo),
                    '--artifact-path',
                    str(artifact_dir),
                    '--database-url',
                    f'sqlite:///{db_path}',
                    '--json',
                ],
                cwd=ROOT,
            )

        payload = json.loads(health.stdout)
        if payload.get('ok') is not True:
            fail(f'healthcheck payload did not report ok=true: {payload}')
        if payload.get('database', {}).get('kind') != 'sqlite':
            fail(f'unexpected database payload: {payload}')
        if payload.get('artifacts', {}).get('ai_index') is not True:
            fail(f'healthcheck did not confirm ai-index presence: {payload}')

        backup = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'backup-hosted-registry.py'),
                '--repo-path',
                str(repo),
                '--database-url',
                f'sqlite:///{db_path}',
                '--artifact-path',
                str(artifact_dir),
                '--output-dir',
                str(backup_root),
                '--label',
                'smoke',
                '--json',
            ],
            cwd=ROOT,
        )
        backup_payload = json.loads(backup.stdout)
        backup_dir = Path(backup_payload['backup_dir'])
        if not backup_dir.exists():
            fail(f'backup_dir missing: {backup_dir}')
        for name in ['repo.bundle', 'server.db', 'artifacts.tar.gz', 'manifest.json']:
            path = backup_dir / name
            if not path.exists():
                fail(f'expected backup artifact missing: {path}')
        manifest = json.loads((backup_dir / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('label') != 'smoke':
            fail(f'unexpected manifest label: {manifest}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_healthcheck_failures():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-ops-failures-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)

        shutil.rmtree(artifact_dir)
        with HealthServer() as base_url:
            missing_artifacts = run(
                [
                    sys.executable,
                    str(ROOT / 'scripts' / 'server-healthcheck.py'),
                    '--api-url',
                    base_url,
                    '--repo-path',
                    str(repo),
                    '--artifact-path',
                    str(artifact_dir),
                    '--database-url',
                    f'sqlite:///{db_path}',
                ],
                cwd=ROOT,
                expect=1,
            )
        assert_contains(
            missing_artifacts.stderr + missing_artifacts.stdout,
            'artifact path',
            'missing artifact path failure',
        )

        artifact_dir = prepare_artifacts(tmpdir)
        (artifact_dir / 'ai-index.json').unlink()
        with HealthServer() as base_url:
            missing_ai_index = run(
                [
                    sys.executable,
                    str(ROOT / 'scripts' / 'server-healthcheck.py'),
                    '--api-url',
                    base_url,
                    '--repo-path',
                    str(repo),
                    '--artifact-path',
                    str(artifact_dir),
                    '--database-url',
                    f'sqlite:///{db_path}',
                ],
                cwd=ROOT,
                expect=1,
            )
        assert_contains(missing_ai_index.stderr + missing_ai_index.stdout, 'ai-index.json', 'missing ai-index failure')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_backup_rejects_dirty_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-ops-dirty-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)
        backup_root = tmpdir / 'backups'
        backup_root.mkdir()

        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'backup-hosted-registry.py'),
                '--repo-path',
                str(repo),
                '--database-url',
                f'sqlite:///{db_path}',
                '--artifact-path',
                str(artifact_dir),
                '--output-dir',
                str(backup_root),
            ],
            cwd=ROOT,
            expect=1,
        )
        assert_contains(result.stderr + result.stdout, 'dirty', 'dirty repo rejection')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_healthcheck_and_backup_success()
    scenario_healthcheck_failures()
    scenario_backup_rejects_dirty_repo()
    print('OK: server ops automation checks passed')


if __name__ == '__main__':
    main()
