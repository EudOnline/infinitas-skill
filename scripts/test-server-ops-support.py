#!/usr/bin/env python3
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from test_support.server_ops import HealthServer, prepare_artifacts, prepare_repo, prepare_sqlite_db, run_command


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-server-ops-support-'))
    try:
        repo = prepare_repo(tmpdir)
        db_path = prepare_sqlite_db(tmpdir)
        artifact_dir = prepare_artifacts(tmpdir)

        inside = run_command(['git', 'rev-parse', '--is-inside-work-tree'], cwd=repo)
        if inside.stdout.strip() != 'true':
            fail(f'expected prepared repo to be a git worktree, got {inside.stdout!r}')

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute('select ok from heartbeat').fetchone()
        finally:
            conn.close()
        if row != (1,):
            fail(f'unexpected sqlite fixture contents: {row!r}')

        if not (artifact_dir / 'ai-index.json').exists():
            fail(f'missing ai-index fixture: {artifact_dir}')
        catalog_payload = json.loads((artifact_dir / 'catalog' / 'distributions.json').read_text(encoding='utf-8'))
        if catalog_payload.get('skills') != []:
            fail(f'unexpected catalog payload: {catalog_payload!r}')

        with HealthServer() as base_url:
            payload = json.loads(request.urlopen(f'{base_url}/healthz', timeout=5).read().decode('utf-8'))
        if payload.get('ok') is not True:
            fail(f'unexpected health payload: {payload!r}')

        print('OK: server ops shared support fixtures behave as expected')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    main()
