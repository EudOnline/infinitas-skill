#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'release-fixture'
VERSION = '1.2.3'
SNAPSHOT_FILENAME = '.infinitas-skill-installed-integrity.json'


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


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_env(extra=None):
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


def scaffold_fixture(repo: Path):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': VERSION,
            'status': 'active',
            'summary': f'Fixture skill version {VERSION} for installed integrity history retention tests',
            'owner': 'retention-test',
            'owners': ['retention-test'],
            'author': 'retention-test',
            'review_state': 'approved',
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for installed integrity history retention tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {VERSION}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(VERSION + '\n', encoding='utf-8')
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-19T00:00:00Z',
                    'requested_by': 'retention-test',
                    'note': 'Fixture approval for installed integrity history retention tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-19T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-retention-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    scaffold_fixture(repo)
    write_json(
        repo / 'config' / 'install-integrity-policy.json',
        {
            '$schema': '../schemas/install-integrity-policy.schema.json',
            'schema_version': 1,
            'freshness': {
                'stale_after_hours': 168,
            },
            'history': {
                'max_inline_events': 2,
            },
        },
    )
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Retention Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'retention@example.com'], cwd=repo)
    run(['git', 'remote', 'add', 'origin', str(origin)], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    run(['git', 'push', '-u', 'origin', 'main'], cwd=repo)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', 'build fixture catalog'], cwd=repo)
    run(['git', 'push'], cwd=repo)

    key_path = tmpdir / 'retention-test-key'
    identity = 'retention-test'
    run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', identity, '-f', str(key_path)], cwd=repo)
    with (repo / 'config' / 'allowed_signers').open('a', encoding='utf-8') as handle:
        public_key = Path(str(key_path) + '.pub').read_text(encoding='utf-8').strip()
        handle.write(f'{identity} {public_key}\n')
    run(['git', 'config', 'gpg.format', 'ssh'], cwd=repo)
    run(['git', 'config', 'user.signingkey', str(key_path)], cwd=repo)
    run(['git', 'add', 'config/allowed_signers'], cwd=repo)
    run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo


def release_fixture(repo: Path):
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )


def install_fixture(repo: Path, target_dir: Path):
    run(
        [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', VERSION],
        cwd=repo,
        env=make_env(),
    )


def read_install_manifest(target_dir: Path):
    return json.loads((target_dir / '.infinitas-skill-install-manifest.json').read_text(encoding='utf-8'))


def run_report(repo: Path, target_dir: Path, *, refresh=False):
    command = [
        sys.executable,
        str(repo / 'scripts' / 'report-installed-integrity.py'),
        str(target_dir),
        '--json',
    ]
    if refresh:
        command.insert(-1, '--refresh')
    result = run(command, cwd=repo, env=make_env())
    return json.loads(result.stdout)


def read_snapshot(target_dir: Path):
    path = target_dir / SNAPSHOT_FILENAME
    if not path.exists():
        fail(f'missing installed integrity snapshot {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        target_dir = tmpdir / 'installed'
        target_dir.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_dir)

        payload = None
        for _ in range(4):
            payload = run_report(repo, target_dir, refresh=True)

        if payload is None:
            fail('expected refresh payload after repeated report refreshes')

        manifest = read_install_manifest(target_dir)
        current = ((manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        inline_events = current.get('integrity_events') or []
        if len(inline_events) != 2:
            fail(f'expected retained inline integrity_events length 2, got {current!r}')

        snapshot = read_snapshot(target_dir)
        if snapshot.get('schema_version') != 1:
            fail(f"expected snapshot schema_version 1, got {snapshot!r}")
        if snapshot.get('target_dir') != str(target_dir.resolve()):
            fail(f'expected snapshot target_dir to match install target, got {snapshot!r}')
        policy = snapshot.get('policy') or {}
        if ((policy.get('history') or {}).get('max_inline_events')) != 2:
            fail(f'expected snapshot policy history.max_inline_events 2, got {snapshot!r}')

        skills = snapshot.get('skills')
        if not isinstance(skills, list) or not skills:
            fail(f'expected snapshot skills list, got {snapshot!r}')
        item = next((entry for entry in skills if entry.get('name') == FIXTURE_NAME), None)
        if item is None:
            fail(f'missing snapshot skill entry for {FIXTURE_NAME!r}: {snapshot!r}')
        if item.get('integrity_events') != inline_events:
            fail(f'expected snapshot inline integrity_events to match manifest, got {item!r}')
        archived = item.get('archived_integrity_events')
        if not isinstance(archived, list) or len(archived) < 3:
            fail(f'expected archived_integrity_events to retain overflow history, got {item!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: installed integrity history retention checks passed')


if __name__ == '__main__':
    main()
