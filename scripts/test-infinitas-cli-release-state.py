#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = 'operate-infinitas-skill'
MODE = 'local-preflight'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run_release_state(command):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode not in {0, 1}:
        fail(
            f'command {command!r} exited {result.returncode}, expected 0 or 1\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def run_release_probe(args, probe_modules):
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
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    return subprocess.run([sys.executable, '-c', script], cwd=ROOT, text=True, capture_output=True, env=env)


def load_payload(result, label):
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def main():
    cli = run_release_state(
        [
            'infinitas',
            'release',
            'check-state',
            SKILL_NAME,
            '--mode',
            MODE,
            '--json',
        ]
    )
    legacy = run_release_state(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check-release-state.py'),
            SKILL_NAME,
            '--mode',
            MODE,
            '--json',
        ]
    )

    cli_payload = load_payload(cli, 'infinitas CLI')
    legacy_payload = load_payload(legacy, 'legacy check-release-state.py')

    if cli.returncode != legacy.returncode:
        fail(f'CLI exit code {cli.returncode} != legacy exit code {legacy.returncode}')

    for field in ['mode', 'release_ready']:
        if cli_payload.get(field) != legacy_payload.get(field):
            fail(f'field {field!r} mismatch: cli={cli_payload.get(field)!r}, legacy={legacy_payload.get(field)!r}')

    cli_skill = (cli_payload.get('skill') or {}).get('name')
    legacy_skill = (legacy_payload.get('skill') or {}).get('name')
    if cli_skill != legacy_skill:
        fail(f'skill.name mismatch: cli={cli_skill!r}, legacy={legacy_skill!r}')

    cli_tag = ((cli_payload.get('git') or {}).get('expected_tag'))
    legacy_tag = ((legacy_payload.get('git') or {}).get('expected_tag'))
    if cli_tag != legacy_tag:
        fail(f'git.expected_tag mismatch: cli={cli_tag!r}, legacy={legacy_tag!r}')

    probe = run_release_probe(
        ['release', 'check-state', SKILL_NAME, '--mode', MODE, '--json'],
        ['policy_trace_lib', 'infinitas_skill.release.service', 'infinitas_skill.release.formatting'],
    )
    if probe.returncode != 0:
        fail(f'release ownership probe failed\nstdout:\n{probe.stdout}\nstderr:\n{probe.stderr}')
    probe_payload = load_payload(probe, 'release ownership probe')
    if probe_payload.get('returncode') not in {0, 1}:
        fail(
            f'release ownership probe command returned {probe_payload.get("returncode")}, expected 0 or 1\n'
            f'stdout:\n{probe_payload.get("stdout")}\n'
            f'stderr:\n{probe_payload.get("stderr")}'
        )
    modules = probe_payload.get('modules') or {}
    if modules.get('policy_trace_lib'):
        fail('release CLI still imports legacy policy_trace_lib directly from scripts/')
    for module_name in ['infinitas_skill.release.service', 'infinitas_skill.release.formatting']:
        if not modules.get(module_name):
            fail(f'release CLI did not route through {module_name}')

    print('OK: infinitas release check-state CLI mirrors legacy script output')


if __name__ == '__main__':
    main()
