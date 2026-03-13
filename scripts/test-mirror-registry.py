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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-mirror-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    mirror = tmpdir / 'mirror.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            '.git',
            '.worktrees',
            '.planning',
            '__pycache__',
            '.cache',
            'scripts/__pycache__',
            '.state',
            'infinitas_hosted_registry.egg-info',
        ),
    )
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '--bare', str(mirror)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Mirror Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'mirror@example.com'], cwd=repo)
    run(['git', 'remote', 'add', 'origin', str(origin)], cwd=repo)
    run(['git', 'remote', 'add', 'github-mirror', str(mirror)], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    run(['git', 'push', '-u', 'origin', 'main'], cwd=repo)
    return tmpdir, repo


def scenario_mirror_helper_and_ops_docs():
    tmpdir, repo = prepare_repo()
    try:
        mirror_script = repo / 'scripts' / 'mirror-registry.sh'
        ok = run([str(mirror_script), '--remote', 'github-mirror', '--dry-run'], cwd=repo)
        combined = ok.stdout + ok.stderr
        assert_contains(combined, 'one-way mirror', 'dry-run output')
        assert_contains(combined, 'git push', 'dry-run output')

        missing_remote = run([str(mirror_script), '--remote', 'missing-remote', '--dry-run'], cwd=repo, expect=1)
        assert_contains(missing_remote.stderr + missing_remote.stdout, 'missing remote', 'missing remote error')

        (repo / 'DIRTY.txt').write_text('dirty\n', encoding='utf-8')
        dirty = run([str(mirror_script), '--remote', 'github-mirror', '--dry-run'], cwd=repo, expect=1)
        assert_contains(dirty.stderr + dirty.stdout, 'dirty', 'dirty tree error')
        (repo / 'DIRTY.txt').unlink()

        reverse = run([str(mirror_script), '--remote', 'github-mirror', '--dry-run', '--fetch'], cwd=repo, expect=1)
        assert_contains(reverse.stderr + reverse.stdout, 'reverse sync', 'reverse sync rejection')

        deployment_doc = (repo / 'docs' / 'ops' / 'server-deployment.md').read_text(encoding='utf-8')
        backup_doc = (repo / 'docs' / 'ops' / 'server-backup-and-restore.md').read_text(encoding='utf-8')
        assert_contains(deployment_doc, 'one-way mirror', 'deployment doc')
        assert_contains(deployment_doc, 'reverse proxy', 'deployment doc')
        assert_contains(backup_doc, 'repo', 'backup doc')
        assert_contains(backup_doc, 'db', 'backup doc')
        assert_contains(backup_doc, 'artifacts', 'backup doc')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_mirror_helper_and_ops_docs()
    print('OK: mirror registry checks passed')


if __name__ == '__main__':
    main()
