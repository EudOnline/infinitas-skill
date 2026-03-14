#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def parse_json_or_fail(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f'{label} did not return JSON\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


class ConfigurableHandler(BaseHTTPRequestHandler):
    requests = []
    status_code = 200

    def do_POST(self):
        length = int(self.headers.get('content-length') or '0')
        payload = self.rfile.read(length)
        self.__class__.requests.append(
            {
                'path': self.path,
                'headers': dict(self.headers.items()),
                'payload': payload.decode('utf-8'),
            }
        )
        self.send_response(self.__class__.status_code)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, fmt, *args):
        return


def create_warning_db(tmpdir: Path) -> Path:
    db_path = tmpdir / 'alerts.db'
    engine = create_engine(f'sqlite:///{db_path}', future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username='ops', display_name='Ops User', role='maintainer', token='ops-token')
        session.add(user)
        session.commit()
        session.refresh(user)

        submission = Submission(
            skill_name='warning-skill',
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

        session.add(
            Job(
                kind='publish_submission',
                status='completed',
                payload_json='{}',
                submission_id=submission.id,
                requested_by_user_id=user.id,
                note='published with warning',
                log='WARNING: publish mirror hook failed: missing remote github-mirror\ncompleted at 2026-03-14T00:00:00Z',
            )
        )
        session.commit()
    return db_path


def start_server(status_code: int):
    ConfigurableHandler.requests = []
    ConfigurableHandler.status_code = status_code
    server = ThreadingHTTPServer(('127.0.0.1', 0), ConfigurableHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def scenario_failed_webhook_writes_fallback():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-alert-fallback-test-'))
    server = None
    thread = None
    try:
        db_path = create_warning_db(tmpdir)
        fallback_path = tmpdir / 'fallback' / 'latest-alert.json'
        server, thread = start_server(status_code=500)
        webhook_url = f'http://127.0.0.1:{server.server_address[1]}/notify'

        alerted = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-warning-jobs',
                '0',
                '--alert-webhook-url',
                webhook_url,
                '--alert-fallback-file',
                str(fallback_path),
                '--json',
            ],
            cwd=ROOT,
            expect=2,
        )
        payload = parse_json_or_fail(alerted, 'alerted inspect fallback run')
        notification = payload.get('notification') or {}
        if notification.get('delivered') is not False:
            fail(f'expected failed webhook delivery metadata: {payload}')
        fallback = notification.get('fallback') or {}
        if fallback.get('written') is not True:
            fail(f'expected fallback metadata to show written=true: {payload}')
        if not fallback_path.exists():
            fail(f'expected fallback file to exist: {fallback_path}')
        fallback_payload = json.loads(fallback_path.read_text(encoding='utf-8'))
        alert_kinds = {item.get('kind') for item in (fallback_payload.get('alerts') or [])}
        if 'warning_jobs' not in alert_kinds:
            fail(f'expected warning_jobs alert in fallback payload: {fallback_payload}')
        delivered = ((fallback_payload.get('notification') or {}).get('delivered'))
        if delivered is not False:
            fail(f'expected fallback payload to record delivery failure: {fallback_payload}')
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_successful_webhook_skips_fallback():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-alert-fallback-success-'))
    server = None
    thread = None
    try:
        db_path = create_warning_db(tmpdir)
        fallback_path = tmpdir / 'fallback' / 'latest-alert.json'
        server, thread = start_server(status_code=200)
        webhook_url = f'http://127.0.0.1:{server.server_address[1]}/notify'

        alerted = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-warning-jobs',
                '0',
                '--alert-webhook-url',
                webhook_url,
                '--alert-fallback-file',
                str(fallback_path),
                '--json',
            ],
            cwd=ROOT,
            expect=2,
        )
        payload = parse_json_or_fail(alerted, 'successful webhook inspect run')
        notification = payload.get('notification') or {}
        if notification.get('delivered') is not True:
            fail(f'expected delivered webhook metadata: {payload}')
        fallback = notification.get('fallback') or {}
        if fallback.get('written') is True:
            fail(f'expected no fallback write on successful delivery: {payload}')
        if fallback_path.exists():
            fail(f'expected fallback file to stay absent on successful delivery: {fallback_path}')
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_fallback_file():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-alert-fallback-render-'))
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
                '--inspect-alert-fallback-file',
                '/var/lib/infinitas/alerts/latest-inspect-alert.json',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')
        inspect_service_text = (output_dir / f'{prefix}-inspect.service').read_text(encoding='utf-8')
        assert_contains(inspect_service_text, '--alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json', 'inspect service')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_failed_webhook_writes_fallback()
    scenario_successful_webhook_skips_fallback()
    scenario_render_fallback_file()
    print('OK: hosted alert fallback file checks passed')


if __name__ == '__main__':
    main()
