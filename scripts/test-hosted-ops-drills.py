#!/usr/bin/env python3
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.models import Base, Job, Submission, User

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


def prepare_repo(base: Path) -> Path:
    repo = base / 'repo'
    repo.mkdir()
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Ops Drill Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'ops-drill@example.com'], cwd=repo)
    (repo / 'README.md').write_text('restore rehearsal fixture\n', encoding='utf-8')
    run(['git', 'add', 'README.md'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    return repo


def prepare_sqlite_db(base: Path) -> Path:
    db_path = base / 'server.db'
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('create table if not exists heartbeat (ok integer)')
        conn.execute('insert into heartbeat(ok) values (1)')
        conn.commit()
    finally:
        conn.close()
    return db_path


def prepare_artifacts(base: Path) -> Path:
    artifact_dir = base / 'artifacts'
    (artifact_dir / 'catalog').mkdir(parents=True)
    (artifact_dir / 'ai-index.json').write_text(json.dumps({'skills': []}), encoding='utf-8')
    (artifact_dir / 'catalog' / 'distributions.json').write_text(json.dumps({'skills': []}), encoding='utf-8')
    return artifact_dir


def create_backup_fixture(tmpdir: Path) -> Path:
    repo = prepare_repo(tmpdir)
    db_path = prepare_sqlite_db(tmpdir)
    artifact_dir = prepare_artifacts(tmpdir)
    backups_dir = tmpdir / 'backups'
    backups_dir.mkdir()
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
            str(backups_dir),
            '--label',
            'drill',
            '--json',
        ],
        cwd=ROOT,
    )
    payload = json.loads(result.stdout)
    return Path(payload['backup_dir'])


def scenario_restore_rehearsal_success_and_failures():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ops-drill-restore-'))
    try:
        backup_dir = create_backup_fixture(tmpdir)
        restore_dir = tmpdir / 'restore-output'
        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'rehearse-hosted-restore.py'),
                '--backup-dir',
                str(backup_dir),
                '--output-dir',
                str(restore_dir),
                '--json',
            ],
            cwd=ROOT,
        )
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'restore rehearsal payload did not report ok=true: {payload}')
        if payload.get('manifest', {}).get('label') != 'drill':
            fail(f'unexpected rehearsal label: {payload}')

        restored_repo = Path(payload['paths']['repo'])
        restored_db = Path(payload['paths']['database'])
        restored_artifacts = Path(payload['paths']['artifacts'])
        if not (restored_repo / 'README.md').exists():
            fail(f'restored repo missing README.md: {restored_repo}')
        if not restored_db.exists():
            fail(f'restored sqlite copy missing: {restored_db}')
        if not (restored_artifacts / 'ai-index.json').exists():
            fail(f'restored artifacts missing ai-index.json: {restored_artifacts}')
        if not (restored_artifacts / 'catalog').is_dir():
            fail(f'restored artifacts missing catalog/: {restored_artifacts}')

        missing_manifest_dir = tmpdir / 'missing-manifest'
        shutil.copytree(backup_dir, missing_manifest_dir)
        (missing_manifest_dir / 'manifest.json').unlink()
        missing_manifest = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'rehearse-hosted-restore.py'),
                '--backup-dir',
                str(missing_manifest_dir),
                '--output-dir',
                str(tmpdir / 'unused-one'),
            ],
            cwd=ROOT,
            expect=1,
        )
        assert_contains(missing_manifest.stderr + missing_manifest.stdout, 'manifest.json', 'missing manifest failure')

        missing_bundle_dir = tmpdir / 'missing-bundle'
        shutil.copytree(backup_dir, missing_bundle_dir)
        manifest = json.loads((missing_bundle_dir / 'manifest.json').read_text(encoding='utf-8'))
        bundle_name = manifest['repo']['bundle']
        (missing_bundle_dir / bundle_name).unlink()
        missing_bundle = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'rehearse-hosted-restore.py'),
                '--backup-dir',
                str(missing_bundle_dir),
                '--output-dir',
                str(tmpdir / 'unused-two'),
            ],
            cwd=ROOT,
            expect=1,
        )
        assert_contains(missing_bundle.stderr + missing_bundle.stdout, bundle_name, 'missing bundle failure')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def create_hosted_state_db(tmpdir: Path) -> Path:
    db_path = tmpdir / 'hosted-state.db'
    engine = create_engine(f'sqlite:///{db_path}', future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username='ops', display_name='Ops User', role='maintainer', token='ops-token')
        session.add(user)
        session.commit()
        session.refresh(user)

        draft = Submission(skill_name='draft-skill', publisher='lvxiaoer', status='draft', payload_json='{}', status_log_json='[]', created_by_user_id=user.id, updated_by_user_id=user.id)
        published = Submission(skill_name='published-skill', publisher='lvxiaoer', status='published', payload_json='{}', status_log_json='[]', created_by_user_id=user.id, updated_by_user_id=user.id)
        session.add_all([draft, published])
        session.commit()
        session.refresh(draft)
        session.refresh(published)

        session.add_all(
            [
                Job(kind='validate_submission', status='queued', payload_json='{}', submission_id=draft.id, requested_by_user_id=user.id, note='queued'),
                Job(kind='publish_submission', status='failed', payload_json='{}', submission_id=published.id, requested_by_user_id=user.id, note='failed', error_message='publish failed badly'),
                Job(kind='promote_submission', status='completed', payload_json='{}', submission_id=published.id, requested_by_user_id=user.id, note='done'),
            ]
        )
        session.commit()
    return db_path


def scenario_state_inspection():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ops-drill-state-'))
    try:
        db_path = create_hosted_state_db(tmpdir)
        result = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--json',
            ],
            cwd=ROOT,
        )
        payload = json.loads(result.stdout)
        if payload.get('jobs', {}).get('total') != 3:
            fail(f'unexpected job total: {payload}')
        if payload.get('jobs', {}).get('by_status', {}).get('queued') != 1:
            fail(f'unexpected queued job count: {payload}')
        if payload.get('jobs', {}).get('by_status', {}).get('failed') != 1:
            fail(f'unexpected failed job count: {payload}')
        failed_jobs = payload.get('jobs', {}).get('recent_failed') or []
        if not failed_jobs or failed_jobs[0].get('error_message') != 'publish failed badly':
            fail(f'unexpected failed job payload: {payload}')
        if payload.get('submissions', {}).get('by_status', {}).get('draft') != 1:
            fail(f'unexpected submission status counts: {payload}')
        if payload.get('submissions', {}).get('by_status', {}).get('published') != 1:
            fail(f'unexpected submission status counts: {payload}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_restore_rehearsal_success_and_failures()
    scenario_state_inspection()
    print('OK: hosted ops drill checks passed')


if __name__ == '__main__':
    main()
