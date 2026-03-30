from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _fail(message):
    raise SystemExit(f'FAIL: {message}')


def run_command(command, *, cwd: Path, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if expect is not None and result.returncode != expect:
        _fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def prepare_repo(base: Path) -> Path:
    repo = base / 'repo'
    repo.mkdir()
    run_command(['git', 'init', '-b', 'main'], cwd=repo)
    run_command(['git', 'config', 'user.name', 'Ops Fixture'], cwd=repo)
    run_command(['git', 'config', 'user.email', 'ops@example.com'], cwd=repo)
    (repo / 'README.md').write_text('fixture repo\n', encoding='utf-8')
    run_command(['git', 'add', 'README.md'], cwd=repo)
    run_command(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
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


class _HealthHandler(BaseHTTPRequestHandler):
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
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _HealthHandler)
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
