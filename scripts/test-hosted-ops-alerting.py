#!/usr/bin/env python3
import json
import shutil
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


def parse_json_or_fail(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f'{label} did not return JSON\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def create_alerting_db(tmpdir: Path) -> Path:
    db_path = tmpdir / 'alerting.db'
    engine = create_engine(f'sqlite:///{db_path}', future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username='ops', display_name='Ops User', role='maintainer', token='ops-token')
        session.add(user)
        session.commit()
        session.refresh(user)

        submission = Submission(
            skill_name='published-skill',
            publisher='lvxiaoer',
            status='published',
            payload_json='{}',
            status_log_json='[]',
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)

        session.add_all(
            [
                Job(kind='validate_submission', status='queued', payload_json='{}', submission_id=submission.id, requested_by_user_id=user.id, note='queued one'),
                Job(kind='promote_submission', status='queued', payload_json='{}', submission_id=submission.id, requested_by_user_id=user.id, note='queued two'),
                Job(kind='publish_submission', status='failed', payload_json='{}', submission_id=submission.id, requested_by_user_id=user.id, note='failed', error_message='publish failed badly'),
            ]
        )
        session.commit()
    return db_path


def scenario_alert_threshold_exit_codes():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ops-alerting-thresholds-'))
    try:
        db_path = create_alerting_db(tmpdir)

        alerted = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-queued-jobs',
                '1',
                '--max-failed-jobs',
                '0',
                '--json',
            ],
            cwd=ROOT,
            expect=2,
        )
        payload = parse_json_or_fail(alerted, 'alerted inspect run')
        if payload.get('ok') is not False:
            fail(f'expected ok=false for alerting payload: {payload}')
        alerts = payload.get('alerts') or []
        if len(alerts) < 2:
            fail(f'expected at least two alerts, got: {payload}')
        kinds = {item.get('kind') for item in alerts}
        if 'queued_jobs' not in kinds or 'failed_jobs' not in kinds:
            fail(f'expected queued_jobs and failed_jobs alerts, got: {payload}')

        calm = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-queued-jobs',
                '5',
                '--max-failed-jobs',
                '2',
                '--json',
            ],
            cwd=ROOT,
        )
        calm_payload = parse_json_or_fail(calm, 'calm inspect run')
        if calm_payload.get('ok') is not True:
            fail(f'expected ok=true for calm payload: {calm_payload}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_inspect_units():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ops-alerting-render-'))
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
                '--database-url',
                'sqlite:////srv/infinitas/data/server.db',
                '--inspect-on-calendar',
                'hourly',
                '--inspect-limit',
                '12',
                '--inspect-max-queued-jobs',
                '4',
                '--inspect-max-running-jobs',
                '2',
                '--inspect-max-failed-jobs',
                '0',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')

        inspect_service = output_dir / f'{prefix}-inspect.service'
        inspect_timer = output_dir / f'{prefix}-inspect.timer'
        if not inspect_service.exists():
            fail(f'missing inspect service: {inspect_service}')
        if not inspect_timer.exists():
            fail(f'missing inspect timer: {inspect_timer}')

        inspect_service_text = inspect_service.read_text(encoding='utf-8')
        inspect_timer_text = inspect_timer.read_text(encoding='utf-8')
        assert_contains(inspect_service_text, 'inspect-hosted-state.py', 'inspect service')
        assert_contains(inspect_service_text, '--max-queued-jobs 4', 'inspect service')
        assert_contains(inspect_service_text, '--max-running-jobs 2', 'inspect service')
        assert_contains(inspect_service_text, '--max-failed-jobs 0', 'inspect service')
        assert_contains(inspect_service_text, 'sqlite:////srv/infinitas/data/server.db', 'inspect service')
        assert_contains(inspect_timer_text, 'OnCalendar=hourly', 'inspect timer')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_alert_threshold_exit_codes()
    scenario_render_inspect_units()
    print('OK: hosted ops alerting checks passed')


if __name__ == '__main__':
    import subprocess
    import sys

    main()
