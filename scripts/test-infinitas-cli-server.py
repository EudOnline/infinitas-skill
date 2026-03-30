#!/usr/bin/env python3
import json
import os
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
    env['PYTHONPATH'] = str(ROOT / 'src')
    return run([sys.executable, '-m', 'infinitas_skill.cli.main', *args], expect=expect, env=env)


def run_legacy(script_name, args, *, expect=None):
    return run([sys.executable, str(ROOT / 'scripts' / script_name), *args], expect=expect)


def prepare_repo(base: Path) -> Path:
    repo = base / 'repo'
    repo.mkdir()
    run(['git', 'init', '-b', 'main'], cwd=repo, expect=0)
    run(['git', 'config', 'user.name', 'Ops Fixture'], cwd=repo, expect=0)
    run(['git', 'config', 'user.email', 'ops@example.com'], cwd=repo, expect=0)
    (repo / 'README.md').write_text('fixture repo\n', encoding='utf-8')
    run(['git', 'add', 'README.md'], cwd=repo, expect=0)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo, expect=0)
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


def load_json_output(result, *, label):
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def scenario_server_cli_surface():
    result = run_cli(['server', '--help'], expect=0)
    help_text = result.stdout + result.stderr
    for command in ['healthcheck', 'backup', 'render-systemd']:
        if command not in help_text:
            fail(f'expected {command!r} in infinitas server help')


def scenario_healthcheck_matches_legacy():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-cli-server-health-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)
        with HealthServer() as base_url:
            args = [
                '--api-url',
                base_url,
                '--repo-path',
                str(repo),
                '--artifact-path',
                str(artifact_dir),
                '--database-url',
                f'sqlite:///{db_path}',
                '--json',
            ]
            cli = run_cli(['server', 'healthcheck', *args], expect=0)
            legacy = run_legacy('server-healthcheck.py', args, expect=0)

        cli_payload = load_json_output(cli, label='infinitas server healthcheck')
        legacy_payload = load_json_output(legacy, label='legacy server-healthcheck.py')
        if cli_payload != legacy_payload:
            fail(f'healthcheck payload mismatch\ncli:\n{cli.stdout}\nlegacy:\n{legacy.stdout}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_backup_matches_legacy():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-cli-server-backup-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)
        cli_root = tmpdir / 'cli-backups'
        legacy_root = tmpdir / 'legacy-backups'
        cli_root.mkdir()
        legacy_root.mkdir()
        common_args = [
            '--repo-path',
            str(repo),
            '--database-url',
            f'sqlite:///{db_path}',
            '--artifact-path',
            str(artifact_dir),
            '--label',
            'smoke',
            '--json',
        ]
        cli = run_cli(['server', 'backup', *common_args, '--output-dir', str(cli_root)], expect=0)
        legacy = run_legacy('backup-hosted-registry.py', [*common_args, '--output-dir', str(legacy_root)], expect=0)

        cli_payload = load_json_output(cli, label='infinitas server backup')
        legacy_payload = load_json_output(legacy, label='legacy backup-hosted-registry.py')
        if cli_payload.get('ok') is not True or legacy_payload.get('ok') is not True:
            fail(f'expected backup ok=true\ncli={cli_payload}\nlegacy={legacy_payload}')
        if cli_payload.get('files') != legacy_payload.get('files'):
            fail(f'backup files payload mismatch\ncli={cli_payload}\nlegacy={legacy_payload}')

        cli_manifest = json.loads(Path(cli_payload['manifest']).read_text(encoding='utf-8'))
        legacy_manifest = json.loads(Path(legacy_payload['manifest']).read_text(encoding='utf-8'))
        if cli_manifest.get('label') != legacy_manifest.get('label'):
            fail(f'backup manifest label mismatch\ncli={cli_manifest}\nlegacy={legacy_manifest}')
        if cli_manifest.get('repo', {}).get('head') != legacy_manifest.get('repo', {}).get('head'):
            fail(f'backup manifest repo head mismatch\ncli={cli_manifest}\nlegacy={legacy_manifest}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_systemd_matches_legacy():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-cli-server-render-'))
    try:
        cli_output = tmpdir / 'cli-rendered'
        legacy_output = tmpdir / 'legacy-rendered'
        shared_args = [
            '--repo-root',
            '/srv/infinitas/repo',
            '--python-bin',
            '/opt/infinitas/.venv/bin/python',
            '--env-file',
            '/etc/infinitas/hosted-registry.env',
            '--service-prefix',
            'infinitas-hosted',
            '--backup-output-dir',
            '/srv/infinitas/backups',
            '--backup-on-calendar',
            'daily',
            '--backup-label',
            'nightly',
        ]
        cli = run_cli(['server', 'render-systemd', '--output-dir', str(cli_output), *shared_args], expect=0)
        legacy = run_legacy('render-hosted-systemd.py', ['--output-dir', str(legacy_output), *shared_args], expect=0)

        if 'wrote' not in cli.stdout or 'wrote' not in legacy.stdout:
            fail(f'expected render output to mention wrote\ncli={cli.stdout}\nlegacy={legacy.stdout}')

        cli_files = sorted(path.name for path in cli_output.iterdir())
        legacy_files = sorted(path.name for path in legacy_output.iterdir())
        if cli_files != legacy_files:
            fail(f'rendered file list mismatch\ncli={cli_files}\nlegacy={legacy_files}')

        sample = 'infinitas-hosted-backup.service'
        cli_text = (cli_output / sample).read_text(encoding='utf-8')
        legacy_text = (legacy_output / sample).read_text(encoding='utf-8')
        if cli_text != legacy_text:
            fail(f'rendered service content mismatch for {sample}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_server_cli_surface()
    scenario_healthcheck_matches_legacy()
    scenario_backup_matches_legacy()
    scenario_render_systemd_matches_legacy()
    print('OK: infinitas server CLI mirrors legacy server ops scripts')


if __name__ == '__main__':
    main()
