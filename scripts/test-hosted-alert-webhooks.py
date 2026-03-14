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


class CaptureHandler(BaseHTTPRequestHandler):
    requests = []

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
        self.send_response(200)
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


def start_capture_server():
    CaptureHandler.requests = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def scenario_alert_webhook_delivery():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-alert-webhook-test-'))
    server = None
    thread = None
    try:
        db_path = create_warning_db(tmpdir)
        server, thread = start_capture_server()
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
                '--json',
            ],
            cwd=ROOT,
            expect=2,
        )
        payload = parse_json_or_fail(alerted, 'alerted inspect webhook run')
        if payload.get('ok') is not False:
            fail(f'expected ok=false for alerting payload: {payload}')
        notification = payload.get('notification') or {}
        if notification.get('delivered') is not True:
            fail(f'expected delivered webhook metadata: {payload}')
        if len(CaptureHandler.requests) != 1:
            fail(f'expected exactly one webhook delivery, got {CaptureHandler.requests!r}')
        delivered_payload = json.loads(CaptureHandler.requests[0]['payload'])
        alert_kinds = {item.get('kind') for item in (delivered_payload.get('alerts') or [])}
        if 'warning_jobs' not in alert_kinds:
            fail(f'expected warning_jobs in delivered webhook payload: {delivered_payload}')

        calm = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'inspect-hosted-state.py'),
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-warning-jobs',
                '5',
                '--alert-webhook-url',
                webhook_url,
                '--json',
            ],
            cwd=ROOT,
        )
        calm_payload = parse_json_or_fail(calm, 'calm inspect webhook run')
        if calm_payload.get('ok') is not True:
            fail(f'expected calm payload ok=true: {calm_payload}')
        if len(CaptureHandler.requests) != 1:
            fail(f'expected no extra webhook delivery for calm run: {CaptureHandler.requests!r}')
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_webhook_inspect_service():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-alert-webhook-render-'))
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
                '--inspect-alert-webhook-url',
                'https://ops.example/hooks/infinitas',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')
        inspect_service_text = (output_dir / f'{prefix}-inspect.service').read_text(encoding='utf-8')
        assert_contains(inspect_service_text, '--alert-webhook-url https://ops.example/hooks/infinitas', 'inspect service')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_alert_webhook_delivery()
    scenario_render_webhook_inspect_service()
    print('OK: hosted alert webhook checks passed')


if __name__ == '__main__':
    main()
