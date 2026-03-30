#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'


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


def cli_env(extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    existing_pythonpath = env.get('PYTHONPATH', '')
    pythonpath = os.pathsep.join([str(ROOT), str(SRC)])
    env['PYTHONPATH'] = f'{pythonpath}{os.pathsep}{existing_pythonpath}' if existing_pythonpath else pythonpath
    return env


def run_server_cli(args, *, cwd=ROOT, expect=0, env=None):
    return run(
        [sys.executable, '-m', 'infinitas_skill.cli.main', 'server', *args],
        cwd=cwd,
        expect=expect,
        env=cli_env(env),
    )


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def parse_json_or_fail(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f'{label} did not return JSON\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def create_backup_dir(root: Path, name: str):
    backup_dir = root / name
    backup_dir.mkdir(parents=True)
    (backup_dir / 'manifest.json').write_text(json.dumps({'created_at': name.split('-')[0]}, ensure_ascii=False) + '\n', encoding='utf-8')
    return backup_dir


def scenario_prune_old_backups():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-backup-retention-test-'))
    try:
        backup_root = tmpdir / 'backups'
        backup_root.mkdir()
        old_one = create_backup_dir(backup_root, '20260314T010000Z-nightly')
        old_two = create_backup_dir(backup_root, '20260314T020000Z-nightly')
        new_one = create_backup_dir(backup_root, '20260314T030000Z-nightly')
        new_two = create_backup_dir(backup_root, '20260314T040000Z-nightly')
        ignored = backup_root / 'manual-notes'
        ignored.mkdir()

        result = run_server_cli(
            [
                'prune-backups',
                '--backup-root',
                str(backup_root),
                '--keep-last',
                '2',
                '--json',
            ],
        )
        payload = parse_json_or_fail(result, 'prune run')
        if payload.get('ok') is not True:
            fail(f'expected ok=true for prune payload: {payload}')
        if len(payload.get('deleted') or []) != 2:
            fail(f'expected exactly two deleted backups: {payload}')
        if len(payload.get('kept') or []) != 2:
            fail(f'expected exactly two kept backups: {payload}')

        deleted_names = {Path(item).name for item in payload.get('deleted') or []}
        kept_names = {Path(item).name for item in payload.get('kept') or []}
        ignored_names = {Path(item).name for item in payload.get('ignored') or []}

        if deleted_names != {old_one.name, old_two.name}:
            fail(f'unexpected deleted backups: {payload}')
        if kept_names != {new_one.name, new_two.name}:
            fail(f'unexpected kept backups: {payload}')
        if ignored.name not in ignored_names:
            fail(f'expected ignored directory to be reported: {payload}')

        if old_one.exists() or old_two.exists():
            fail('expected old backups to be removed from disk')
        if not new_one.exists() or not new_two.exists():
            fail('expected newest backups to remain on disk')
        if not ignored.exists():
            fail('expected unrelated directory to remain on disk')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_render_prune_units():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-backup-prune-render-'))
    try:
        output_dir = tmpdir / 'rendered'
        prefix = 'infinitas-hosted'
        result = run_server_cli(
            [
                'render-systemd',
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
                '--prune-on-calendar',
                'daily',
                '--prune-keep-last',
                '7',
            ],
        )
        assert_contains(result.stdout, 'wrote', 'render output')

        prune_service = output_dir / f'{prefix}-prune.service'
        prune_timer = output_dir / f'{prefix}-prune.timer'
        if not prune_service.exists():
            fail(f'missing prune service: {prune_service}')
        if not prune_timer.exists():
            fail(f'missing prune timer: {prune_timer}')

        prune_service_text = prune_service.read_text(encoding='utf-8')
        prune_timer_text = prune_timer.read_text(encoding='utf-8')
        assert_contains(prune_service_text, 'Environment=PYTHONPATH=/srv/infinitas/repo/src', 'prune service')
        assert_contains(prune_service_text, '-m infinitas_skill.cli.main server prune-backups', 'prune service')
        assert_contains(prune_service_text, '--backup-root /srv/infinitas/backups', 'prune service')
        assert_contains(prune_service_text, '--keep-last 7', 'prune service')
        assert_contains(prune_timer_text, 'OnCalendar=daily', 'prune timer')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_prune_old_backups()
    scenario_render_prune_units()
    print('OK: hosted backup retention checks passed')


if __name__ == '__main__':
    main()
