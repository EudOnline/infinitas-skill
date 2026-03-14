#!/usr/bin/env python3
import shutil
import subprocess
import sys
import tempfile
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


def scenario_render_mirror_units_and_docs():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-mirror-automation-'))
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
                '--mirror-remote',
                'github-mirror',
                '--mirror-branch',
                'main',
                '--mirror-on-calendar',
                'daily',
            ],
            cwd=ROOT,
        )
        assert_contains(result.stdout, 'wrote', 'render output')

        mirror_service = output_dir / f'{prefix}-mirror.service'
        mirror_timer = output_dir / f'{prefix}-mirror.timer'
        if not mirror_service.exists():
            fail(f'missing mirror service: {mirror_service}')
        if not mirror_timer.exists():
            fail(f'missing mirror timer: {mirror_timer}')

        mirror_service_text = mirror_service.read_text(encoding='utf-8')
        mirror_timer_text = mirror_timer.read_text(encoding='utf-8')
        assert_contains(mirror_service_text, 'mirror-registry.sh', 'mirror service')
        assert_contains(mirror_service_text, '--remote github-mirror', 'mirror service')
        assert_contains(mirror_service_text, '--branch main', 'mirror service')
        assert_contains(mirror_timer_text, 'OnCalendar=daily', 'mirror timer')

        deployment_doc = (ROOT / 'docs' / 'ops' / 'server-deployment.md').read_text(encoding='utf-8')
        assert_contains(deployment_doc, 'mirror.timer', 'deployment doc')
        assert_contains(deployment_doc, 'one-way', 'deployment doc')
        assert_contains(deployment_doc, 'enable --now infinitas-hosted-mirror.timer', 'deployment doc')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_render_mirror_units_and_docs()
    print('OK: hosted mirror automation checks passed')


if __name__ == '__main__':
    main()
