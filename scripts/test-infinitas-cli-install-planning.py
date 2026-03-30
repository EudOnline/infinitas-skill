#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, *, env=None):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-cli-install-planning-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare_target(repo: Path) -> Path:
    target = repo / '.tmp-installed-skills'
    target.mkdir(parents=True, exist_ok=True)
    skill_dir = target / 'demo-skill'
    shutil.copytree(repo / 'templates' / 'basic-skill', skill_dir)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': 'demo-skill',
            'version': '1.2.3',
            'status': 'active',
            'summary': 'Demo installed skill',
            'owner': 'compat-test',
            'owners': ['compat-test'],
            'author': 'compat-test',
            'review_state': 'approved',
        }
    )
    write_json(skill_dir / '_meta.json', meta)
    write_json(
        target / '.infinitas-skill-install-manifest.json',
        {
            'repo': 'https://example.invalid/repo.git',
            'updated_at': '2026-03-12T00:00:00Z',
            'skills': {
                'demo-skill': {
                    'name': 'demo-skill',
                    'version': '1.2.3',
                    'locked_version': '1.2.3',
                    'source_registry': 'self',
                }
            },
            'history': {},
        },
    )
    return target


def run_cli(repo: Path, args: list[str]):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo / 'src')
    return run([sys.executable, '-m', 'infinitas_skill.cli.main', *args], cwd=repo, env=env)


def run_cli_probe(repo: Path, args: list[str], probe_modules: list[str]):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo / 'src')
    script = (
        "import contextlib, io, json, sys\n"
        "from infinitas_skill.cli.main import main\n"
        "stdout = io.StringIO()\n"
        "stderr = io.StringIO()\n"
        "with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):\n"
        f"    code = main({args!r})\n"
        f"payload = {{'returncode': code, 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue(), 'modules': {{name: name in sys.modules for name in {probe_modules!r}}}}}\n"
        "print(json.dumps(payload))\n"
    )
    return run([sys.executable, '-c', script], cwd=repo, env=env)


def assert_same_result(repo: Path, cli_args: list[str], legacy_args: list[str], expect_returncode: int):
    cli = run_cli(repo, cli_args)
    legacy = run([sys.executable, *legacy_args], cwd=repo)

    if cli.returncode != expect_returncode:
        fail(
            f'CLI command returned {cli.returncode}, expected {expect_returncode}\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )
    if legacy.returncode != expect_returncode:
        fail(
            f'legacy command returned {legacy.returncode}, expected {expect_returncode}\n'
            f'stdout:\n{legacy.stdout}\n'
            f'stderr:\n{legacy.stderr}'
        )
    if cli.returncode != legacy.returncode:
        fail(f'CLI exit code {cli.returncode} != legacy exit code {legacy.returncode}')
    if cli.stdout != legacy.stdout:
        fail(f'CLI stdout != legacy stdout\ncli:\n{cli.stdout}\nlegacy:\n{legacy.stdout}')
    if cli.stderr != legacy.stderr:
        fail(f'CLI stderr != legacy stderr\ncli:\n{cli.stderr}\nlegacy:\n{legacy.stderr}')


def assert_package_owned_install_command(repo: Path, cli_args: list[str]):
    probe = run_cli_probe(
        repo,
        cli_args,
        ['dependency_lib', 'infinitas_skill.install.service'],
    )
    if probe.returncode != 0:
        fail(f'ownership probe failed\nstdout:\n{probe.stdout}\nstderr:\n{probe.stderr}')
    payload = json.loads(probe.stdout)
    if payload['returncode'] != 0:
        fail(
            f'ownership probe command returned {payload["returncode"]}, expected 0\n'
            f'stdout:\n{payload["stdout"]}\n'
            f'stderr:\n{payload["stderr"]}'
        )
    if payload['modules'].get('dependency_lib'):
        fail('install CLI still imports legacy dependency_lib directly from scripts/')
    if not payload['modules'].get('infinitas_skill.install.service'):
        fail('install CLI did not route through infinitas_skill.install.service')


def main():
    tmpdir, repo = prepare_repo()
    try:
        target = prepare_target(repo)
        skill_dir = repo / 'templates' / 'basic-skill'

        assert_same_result(
            repo,
            ['install', 'resolve-plan', '--skill-dir', str(skill_dir), '--target-dir', str(target), '--json'],
            [str(repo / 'scripts' / 'resolve-install-plan.py'), '--skill-dir', str(skill_dir), '--target-dir', str(target), '--json'],
            expect_returncode=0,
        )
        assert_same_result(
            repo,
            ['install', 'check-target', str(skill_dir), str(target)],
            [str(repo / 'scripts' / 'check-install-target.py'), str(skill_dir), str(target)],
            expect_returncode=0,
        )
        assert_package_owned_install_command(
            repo,
            ['install', 'resolve-plan', '--skill-dir', str(skill_dir), '--target-dir', str(target), '--json'],
        )
        assert_package_owned_install_command(
            repo,
            ['install', 'check-target', str(skill_dir), str(target)],
        )

        manifest_path = target / '.infinitas-skill-install-manifest.json'
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
        payload['schema_version'] = 999
        write_json(manifest_path, payload)

        assert_same_result(
            repo,
            ['install', 'resolve-plan', '--skill-dir', str(skill_dir), '--target-dir', str(target), '--json'],
            [str(repo / 'scripts' / 'resolve-install-plan.py'), '--skill-dir', str(skill_dir), '--target-dir', str(target), '--json'],
            expect_returncode=1,
        )
        assert_same_result(
            repo,
            ['install', 'check-target', str(skill_dir), str(target)],
            [str(repo / 'scripts' / 'check-install-target.py'), str(skill_dir), str(target)],
            expect_returncode=1,
        )
    finally:
        shutil.rmtree(tmpdir)

    print('OK: infinitas install planning CLI mirrors legacy script output')


if __name__ == '__main__':
    main()
