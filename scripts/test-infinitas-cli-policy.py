#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_SKILL = ROOT / 'skills' / 'active' / 'operate-infinitas-skill'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, *, env=None):
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=env)


def run_cli(args):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / 'src')
    return run([sys.executable, '-m', 'infinitas_skill.cli.main', *args], env=env)


def run_cli_probe(args, probe_modules):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / 'src')
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
    return run([sys.executable, '-c', script], env=env)


def run_legacy(args):
    return run([sys.executable, *args])


def load_json_output(result, *, label):
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def scenario_policy_cli_surface():
    result = run_cli(['policy', '--help'])
    if result.returncode != 0:
        fail(
            f'policy help exited {result.returncode}, expected 0\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    help_text = result.stdout + result.stderr
    for command in ['check-packs', 'check-promotion']:
        if command not in help_text:
            fail(f'expected {command!r} in infinitas policy help')


def scenario_check_policy_packs_matches_legacy():
    cli = run_cli(['policy', 'check-packs'])
    legacy = run_legacy([str(ROOT / 'scripts' / 'check-policy-packs.py')])

    if cli.returncode != legacy.returncode:
        fail(f'check-packs exit code mismatch: cli={cli.returncode}, legacy={legacy.returncode}')
    if cli.stdout != legacy.stdout:
        fail(f'check-packs stdout mismatch\ncli:\n{cli.stdout}\nlegacy:\n{legacy.stdout}')
    if cli.stderr != legacy.stderr:
        fail(f'check-packs stderr mismatch\ncli:\n{cli.stderr}\nlegacy:\n{legacy.stderr}')


def scenario_check_promotion_matches_legacy():
    cli = run_cli(['policy', 'check-promotion', '--json', '--as-active', str(ACTIVE_SKILL)])
    legacy = run_legacy(
        [
            str(ROOT / 'scripts' / 'check-promotion-policy.py'),
            '--json',
            '--as-active',
            str(ACTIVE_SKILL),
        ]
    )

    if cli.returncode != legacy.returncode:
        fail(f'check-promotion exit code mismatch: cli={cli.returncode}, legacy={legacy.returncode}')

    cli_payload = load_json_output(cli, label='infinitas policy check-promotion')
    legacy_payload = load_json_output(legacy, label='legacy check-promotion-policy.py')

    for field in ['passed', 'error_count', 'skill_path']:
        if cli_payload.get(field) != legacy_payload.get(field):
            fail(
                f'check-promotion field {field!r} mismatch: '
                f'cli={cli_payload.get(field)!r}, legacy={legacy_payload.get(field)!r}'
            )

    cli_trace = cli_payload.get('policy_trace') or {}
    legacy_trace = legacy_payload.get('policy_trace') or {}
    for field in ['domain', 'decision', 'summary']:
        if cli_trace.get(field) != legacy_trace.get(field):
            fail(
                f'check-promotion policy_trace.{field} mismatch: '
                f'cli={cli_trace.get(field)!r}, legacy={legacy_trace.get(field)!r}'
            )


def scenario_policy_uses_package_service():
    result = run_cli_probe(
        ['policy', 'check-promotion', '--json', '--as-active', str(ACTIVE_SKILL)],
        ['policy_trace_lib', 'infinitas_skill.policy.service', 'infinitas_skill.policy.trace'],
    )
    if result.returncode != 0:
        fail(f'policy ownership probe failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')
    payload = load_json_output(result, label='policy ownership probe')
    if payload.get('returncode') != 0:
        fail(
            f'policy ownership probe command returned {payload.get("returncode")}, expected 0\n'
            f'stdout:\n{payload.get("stdout")}\n'
            f'stderr:\n{payload.get("stderr")}'
        )
    modules = payload.get('modules') or {}
    if modules.get('policy_trace_lib'):
        fail('policy CLI still imports legacy policy_trace_lib directly from scripts/')
    for module_name in ['infinitas_skill.policy.service', 'infinitas_skill.policy.trace']:
        if not modules.get(module_name):
            fail(f'policy CLI did not route through {module_name}')


def main():
    scenario_policy_cli_surface()
    scenario_check_policy_packs_matches_legacy()
    scenario_check_promotion_matches_legacy()
    scenario_policy_uses_package_service()
    print('OK: infinitas policy CLI mirrors legacy policy scripts')


if __name__ == '__main__':
    main()
