import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_SKILL = ROOT / 'skills' / 'active' / 'operate-infinitas-skill'


def fail(message):
    raise AssertionError(message)


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


def load_json_output(result, *, label):
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        fail(f'{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')


def assert_policy_cli_help_lists_maintained_subcommands():
    result = run_cli(['policy', '--help'])
    if result.returncode != 0:
        fail(
            f'policy help exited {result.returncode}, expected 0\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    help_text = result.stdout + result.stderr
    for command in ['check-packs', 'check-promotion', 'recommend-reviewers', 'review-status']:
        if command not in help_text:
            fail(f'expected {command!r} in infinitas policy help')


def assert_policy_check_packs_reports_success():
    cli = run_cli(['policy', 'check-packs'])
    if cli.returncode != 0:
        fail(
            f'check-packs exited {cli.returncode}, expected 0\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )
    combined = cli.stdout + cli.stderr
    if 'OK:' not in combined:
        fail(f'expected success marker in check-packs output\n{combined}')


def assert_policy_check_promotion_returns_expected_json():
    cli = run_cli(['policy', 'check-promotion', '--json', '--as-active', str(ACTIVE_SKILL)])
    if cli.returncode != 0:
        fail(
            f'check-promotion exited {cli.returncode}, expected 0\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )

    cli_payload = load_json_output(cli, label='infinitas policy check-promotion')
    if cli_payload.get('passed') is not True:
        fail(f'expected check-promotion passed=true, got {cli_payload!r}')
    if cli_payload.get('error_count') != 0:
        fail(f'expected check-promotion error_count=0, got {cli_payload!r}')
    if cli_payload.get('skill_path') not in {str(ACTIVE_SKILL), 'skills/active/operate-infinitas-skill'}:
        fail(f'expected check-promotion skill_path to reference {ACTIVE_SKILL}, got {cli_payload.get("skill_path")!r}')
    cli_trace = cli_payload.get('policy_trace') or {}
    for field in ['domain', 'decision', 'summary']:
        if not cli_trace.get(field):
            fail(f'expected check-promotion policy_trace.{field} in payload, got {cli_trace!r}')


def assert_policy_routes_through_package_service():
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


def assert_policy_recommend_reviewers_returns_expected_json():
    cli = run_cli(['policy', 'recommend-reviewers', '--json', '--as-active', str(ACTIVE_SKILL)])
    if cli.returncode != 0:
        fail(
            f'recommend-reviewers exited {cli.returncode}, expected 0\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )

    cli_payload = load_json_output(cli, label='infinitas policy recommend-reviewers')
    if cli_payload.get('skill') != 'operate-infinitas-skill':
        fail(f'expected recommend-reviewers skill=operate-infinitas-skill, got {cli_payload!r}')
    if not isinstance(cli_payload.get('required_groups'), list):
        fail(f'expected recommend-reviewers required_groups list, got {cli_payload!r}')
    if not isinstance(cli_payload.get('group_recommendations'), list):
        fail(f'expected recommend-reviewers group_recommendations list, got {cli_payload!r}')
    if not isinstance(cli_payload.get('escalations'), list):
        fail(f'expected recommend-reviewers escalations list, got {cli_payload!r}')


def assert_policy_review_status_returns_expected_json():
    cli = run_cli(
        [
            'policy',
            'review-status',
            '--json',
            '--as-active',
            '--show-recommendations',
            str(ACTIVE_SKILL),
        ]
    )
    if cli.returncode not in {0, 1}:
        fail(
            f'review-status exited {cli.returncode}, expected 0 or 1\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )

    cli_payload = load_json_output(cli, label='infinitas policy review-status')
    if cli_payload.get('skill') != 'operate-infinitas-skill':
        fail(f'expected review-status skill=operate-infinitas-skill, got {cli_payload!r}')
    if not isinstance(cli_payload.get('review_gate_pass'), bool):
        fail(f'expected review-status review_gate_pass bool, got {cli_payload!r}')
    recommendations = cli_payload.get('recommendations')
    if not isinstance(recommendations, dict):
        fail(f'expected review-status recommendations object, got {cli_payload!r}')


def assert_policy_review_commands_route_through_package_modules():
    result = run_cli_probe(
        ['policy', 'review-status', '--json', '--as-active', str(ACTIVE_SKILL)],
        [
            'reviewer_rotation_lib',
            'review_lib',
            'infinitas_skill.policy.review_commands',
            'infinitas_skill.policy.reviewer_rotation',
            'infinitas_skill.policy.reviews',
        ],
    )
    if result.returncode != 0:
        fail(
            'policy review command ownership probe failed\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    payload = load_json_output(result, label='policy review command ownership probe')
    if payload.get('returncode') not in {0, 1}:
        fail(
            f'policy review command returned {payload.get("returncode")}, expected 0 or 1\n'
            f'stdout:\n{payload.get("stdout")}\n'
            f'stderr:\n{payload.get("stderr")}'
        )
    modules = payload.get('modules') or {}
    for legacy_module in ['reviewer_rotation_lib', 'review_lib']:
        if modules.get(legacy_module):
            fail(f'policy review command still imports legacy {legacy_module} directly from scripts/')
    for module_name in [
        'infinitas_skill.policy.review_commands',
        'infinitas_skill.policy.reviewer_rotation',
        'infinitas_skill.policy.reviews',
    ]:
        if not modules.get(module_name):
            fail(f'policy review command did not route through {module_name}')


def main():
    assert_policy_cli_help_lists_maintained_subcommands()
    assert_policy_check_packs_reports_success()
    assert_policy_check_promotion_returns_expected_json()
    assert_policy_routes_through_package_service()
    assert_policy_recommend_reviewers_returns_expected_json()
    assert_policy_review_status_returns_expected_json()
    assert_policy_review_commands_route_through_package_modules()
