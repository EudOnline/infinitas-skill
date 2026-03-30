#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.models import Base, Job
from server.modules.access.models import Principal
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.release.models import Release
from server.modules.review.models import ReviewCase


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd=ROOT, expect=None, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if expect is not None and result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def run_cli(args, *, expect=None):
    env = os.environ.copy()
    existing_pythonpath = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = f'{SRC}{os.pathsep}{existing_pythonpath}' if existing_pythonpath else str(SRC)
    return run([sys.executable, '-m', 'infinitas_skill.cli.main', *args], expect=expect, env=env)


def prepare_inspect_db(base: Path) -> Path:
    db_path = base / 'inspect.db'
    engine = create_engine(f'sqlite:///{db_path}', future=True, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        principal = Principal(kind='user', slug='fixture-user', display_name='Fixture User')
        session.add(principal)
        session.flush()

        skill = Skill(
            namespace_id=principal.id,
            slug='fixture-skill',
            display_name='Fixture Skill',
            created_by_principal_id=principal.id,
        )
        session.add(skill)
        session.flush()

        version = SkillVersion(
            skill_id=skill.id,
            version='1.0.0',
            content_digest='sha256:fixture-content',
            metadata_digest='sha256:fixture-metadata',
            created_by_principal_id=principal.id,
        )
        session.add(version)
        session.flush()

        release = Release(skill_version_id=version.id, state='ready')
        session.add(release)
        session.flush()

        exposures = [
            Exposure(release_id=release.id, audience_type='private', state='active', review_requirement='none'),
            Exposure(release_id=release.id, audience_type='public', state='review_open', review_requirement='blocking'),
        ]
        session.add_all(exposures)
        session.flush()

        session.add(ReviewCase(exposure_id=exposures[1].id, mode='blocking', state='open'))

        jobs = [
            Job(
                kind='materialize_release',
                status='queued',
                payload_json=json.dumps({'release_id': release.id}),
                release_id=release.id,
                note='queued fixture job',
            ),
            Job(
                kind='materialize_release',
                status='running',
                payload_json=json.dumps({'release_id': release.id}),
                release_id=release.id,
                log='claimed at 2026-03-30T00:00:00Z\n',
            ),
            Job(
                kind='materialize_release',
                status='failed',
                payload_json=json.dumps({'release_id': release.id}),
                release_id=release.id,
                error_message='mirror push failed',
                log='ERROR: mirror push failed\n',
            ),
            Job(
                kind='materialize_release',
                status='completed',
                payload_json=json.dumps({'release_id': release.id}),
                release_id=release.id,
                log='WARNING: mirror push degraded\ncompleted at 2026-03-30T00:00:00Z\n',
            ),
        ]
        session.add_all(jobs)
        session.commit()

    engine.dispose()
    return db_path


class NotifyHandler(BaseHTTPRequestHandler):
    received = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        payload = self.rfile.read(length).decode('utf-8')
        self.__class__.received.append(
            {
                'path': self.path,
                'body': payload,
                'content_type': self.headers.get('Content-Type', ''),
            }
        )
        response = b'{"ok":true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class NotifyServer:
    def __init__(self):
        NotifyHandler.received = []
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), NotifyHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        host, port = self.server.server_address
        return f'http://{host}:{port}/notify'

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def load_json(result, *, label):
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def scenario_inspect_state_reports_expected_summary():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-inspect-'))
    try:
        db_path = prepare_inspect_db(tmpdir)
        args = [
            '--database-url',
            f'sqlite:///{db_path}',
            '--limit',
            '5',
            '--max-queued-jobs',
            '0',
            '--max-running-jobs',
            '0',
            '--max-failed-jobs',
            '0',
            '--max-warning-jobs',
            '0',
            '--json',
        ]
        cli = run_cli(['server', 'inspect-state', *args], expect=2)
        cli_payload = load_json(cli, label='infinitas server inspect-state')

        counts = cli_payload.get('jobs', {}).get('counts', {})
        for key, expected in [('queued', 1), ('running', 1), ('failed', 1), ('completed', 1), ('warning', 1)]:
            if counts.get(key) != expected:
                fail(f'expected jobs.counts[{key!r}] == {expected}, got {counts}')

        audience = cli_payload.get('releases', {}).get('by_audience', {})
        if audience.get('private') != 1 or audience.get('public') != 1:
            fail(f'unexpected release audience summary: {audience}')

        review_state = cli_payload.get('releases', {}).get('by_audience_review_state', {})
        if review_state.get('public', {}).get('open') != 1:
            fail(f'unexpected public review state summary: {review_state}')

        alert_kinds = {item.get('kind') for item in cli_payload.get('alerts') or []}
        expected_alerts = {'queued_jobs', 'running_jobs', 'failed_jobs', 'warning_jobs'}
        if alert_kinds != expected_alerts:
            fail(f'unexpected alert kinds: {alert_kinds}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_inspect_state_webhook_and_fallback():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-inspect-webhook-'))
    try:
        db_path = prepare_inspect_db(tmpdir)
        fallback_path = tmpdir / 'alerts' / 'latest.json'

        with NotifyServer() as notify:
            result = run_cli(
                [
                    'server',
                    'inspect-state',
                    '--database-url',
                    f'sqlite:///{db_path}',
                    '--limit',
                    '5',
                    '--max-warning-jobs',
                    '0',
                    '--alert-webhook-url',
                    notify.url,
                    '--alert-fallback-file',
                    str(fallback_path),
                    '--json',
                ],
                expect=2,
            )

        payload = load_json(result, label='inspect-state webhook delivery')
        webhook = payload.get('notification', {}).get('webhook', {})
        fallback = payload.get('notification', {}).get('fallback', {})
        if webhook.get('delivered') is not True or webhook.get('status_code') != 200:
            fail(f'expected delivered webhook summary, got {webhook}')
        if fallback.get('attempted') is not False:
            fail(f'fallback should not run after successful webhook delivery: {fallback}')
        if len(NotifyHandler.received) != 1:
            fail(f'expected one webhook delivery, got {NotifyHandler.received!r}')

        unreachable = run_cli(
            [
                'server',
                'inspect-state',
                '--database-url',
                f'sqlite:///{db_path}',
                '--limit',
                '5',
                '--max-warning-jobs',
                '0',
                '--alert-webhook-url',
                'http://127.0.0.1:9/notify',
                '--alert-fallback-file',
                str(fallback_path),
                '--json',
            ],
            expect=2,
        )

        unreachable_payload = load_json(unreachable, label='inspect-state fallback write')
        fallback = unreachable_payload.get('notification', {}).get('fallback', {})
        if fallback.get('wrote') is not True:
            fail(f'expected fallback file write, got {fallback}')
        if not fallback_path.exists():
            fail(f'expected fallback file to exist: {fallback_path}')
        fallback_payload = json.loads(fallback_path.read_text(encoding='utf-8'))
        if fallback_payload != unreachable_payload:
            fail('fallback file content did not match returned summary')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_inspect_state_reports_expected_summary()
    scenario_inspect_state_webhook_and_fallback()
    print('OK: inspect-state CLI behaves as expected')


if __name__ == '__main__':
    main()
