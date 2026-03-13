#!/usr/bin/env python3
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def prepare_repo(base: Path) -> Path:
    repo = base / 'repo'
    repo.mkdir()
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Ops Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'ops@example.com'], cwd=repo)
    (repo / 'README.md').write_text('fixture repo\n', encoding='utf-8')
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
    catalog_dir = artifact_dir / 'catalog'
    catalog_dir.mkdir(parents=True)
    (artifact_dir / 'ai-index.json').write_text(json.dumps({'skills': []}), encoding='utf-8')
    (catalog_dir / 'distributions.json').write_text(json.dumps({'skills': []}), encoding='utf-8')
    return artifact_dir


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == '/healthz':
            payload = json.dumps({'ok': True, 'service': 'fixture-hosted-registry'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()


class HealthServer:
    def __init__(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.server.server_address
        return f'http://{host}:{port}'

    def __enter__(self):
        self.thread.start()
        return self.base_url

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


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
