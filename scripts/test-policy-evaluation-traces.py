#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ACTIVE_SKILL = ROOT / 'skills' / 'active' / 'operate-infinitas-skill'
PROMOTION_FIXTURE = 'promotion-trace-break-glass-fixture'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(command, *, expect=None):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if expect is not None and result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def run_in_repo(repo, command, *, expect=None):
    result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
    if expect is not None and result.returncode != expect:
        fail(
            f'command {command!r} in {repo} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def load_json_output(result, *, command):
    stdout = result.stdout.strip()
    if not stdout:
        fail(
            f'expected JSON output from {command!r}\n'
            f'stderr:\n{result.stderr}'
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        fail(
            f'expected valid JSON output from {command!r}: {exc}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )


def copy_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-policy-trace-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.worktrees', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def rewrite_promotion_policy(repo: Path):
    write_json(
        repo / 'policy' / 'promotion-policy.json',
        {
            '$schema': '../schemas/promotion-policy.schema.json',
            'version': 4,
            'active_requires': {
                'review_state': ['under-review'],
                'require_changelog': True,
                'require_smoke_test': True,
                'require_owner': True,
            },
            'reviews': {
                'require_reviews_file': True,
                'reviewer_must_differ_from_owner': True,
                'block_on_rejection': True,
                'groups': {
                    'maintainers': {
                        'members': ['alice'],
                    },
                    'security': {
                        'members': ['bob'],
                    },
                },
                'quorum': {
                    'defaults': {
                        'min_approvals': 1,
                        'required_groups': [],
                    },
                    'stage_overrides': {
                        'active': {
                            'min_approvals': 1,
                            'required_groups': ['maintainers', 'security'],
                        },
                    },
                },
            },
            'high_risk_active_requires': {
                'min_maintainers': 1,
                'require_requires_block': True,
            },
            'dependency_rules': {
                'allow_name_only_refs': True,
                'allow_version_pins': True,
                'require_resolvable_refs_for_active': True,
                'auto_install_dependencies_default': True,
            },
        },
    )


def scaffold_promotion_fixture(repo: Path):
    skill_dir = repo / 'skills' / 'incubating' / PROMOTION_FIXTURE
    shutil.copytree(repo / 'templates' / 'basic-skill', skill_dir)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': PROMOTION_FIXTURE,
            'publisher': 'fixture',
            'qualified_name': f'fixture/{PROMOTION_FIXTURE}',
            'version': '0.1.0',
            'status': 'incubating',
            'summary': 'Fixture skill for promotion exception trace checks.',
            'owner': 'owner',
            'owners': ['owner'],
            'author': 'owner',
            'maintainers': ['owner'],
            'review_state': 'approved',
            'risk_level': 'low',
        }
    )
    write_json(skill_dir / '_meta.json', meta)
    (skill_dir / 'CHANGELOG.md').write_text('# Changelog\n\n## 0.1.0 - 2026-03-15\n- Added fixture.\n', encoding='utf-8')
    (skill_dir / 'tests').mkdir(exist_ok=True)
    (skill_dir / 'tests' / 'smoke.md').write_text('# Smoke\n\nFixture smoke test.\n', encoding='utf-8')
    write_json(
        skill_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-15T00:00:00Z',
                    'requested_by': 'owner',
                    'note': 'Urgent promotion trace fixture',
                }
            ],
            'entries': [
                {
                    'reviewer': 'alice',
                    'decision': 'approved',
                    'at': '2026-03-15T00:05:00Z',
                    'note': 'Maintainer approved fixture',
                }
            ],
        },
    )
    return skill_dir


def write_exception_policy(repo: Path):
    write_json(
        repo / 'policy' / 'exception-policy.json',
        {
            '$schema': '../schemas/exception-policy.schema.json',
            'version': 1,
            'exceptions': [
                {
                    'id': 'promotion-trace-waiver',
                    'scope': 'promotion',
                    'skills': [PROMOTION_FIXTURE],
                    'rules': ['required-reviewer-groups'],
                    'approved_by': ['incident-commander'],
                    'approved_at': '2026-03-15T00:10:00Z',
                    'justification': 'Trace fixture waiver',
                    'expires_at': '2099-01-01T00:00:00Z',
                }
            ],
        },
    )


def scenario_promotion_policy_trace():
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check-promotion-policy.py'),
        '--json',
        '--as-active',
        str(ACTIVE_SKILL),
    ]
    result = run(command)
    payload = load_json_output(result, command=command)
    trace = payload.get('policy_trace') or {}
    if trace.get('domain') != 'promotion_policy':
        fail(f"expected promotion_policy trace, got {trace.get('domain')!r}")
    for key in ['decision', 'effective_sources', 'applied_rules']:
        if key not in trace:
            fail(f'missing promotion policy trace field {key!r}')


def scenario_promotion_policy_failure_trace():
    tmpdir, repo = copy_repo()
    try:
        skill_dir = repo / 'skills' / 'active' / 'operate-infinitas-skill'
        (skill_dir / 'CHANGELOG.md').unlink()
        command = [
            sys.executable,
            str(repo / 'scripts' / 'check-promotion-policy.py'),
            '--json',
            '--as-active',
            str(skill_dir),
        ]
        result = run_in_repo(repo, command, expect=1)
        payload = load_json_output(result, command=command)
        trace = payload.get('policy_trace') or {}
        if trace.get('decision') != 'deny':
            fail(f"expected deny decision for failing promotion trace, got {trace.get('decision')!r}")
        blocking_rules = trace.get('blocking_rules') or []
        if not blocking_rules:
            fail(f'expected blocking rules for failing promotion trace, got {trace!r}')
        if not any('CHANGELOG' in json.dumps(item, ensure_ascii=False) for item in blocking_rules):
            fail(f'expected failing promotion trace to mention CHANGELOG, got {blocking_rules!r}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_promotion_exception_trace():
    tmpdir, repo = copy_repo()
    try:
        rewrite_promotion_policy(repo)
        skill_dir = scaffold_promotion_fixture(repo)
        write_exception_policy(repo)
        command = [
            sys.executable,
            str(repo / 'scripts' / 'check-promotion-policy.py'),
            '--json',
            '--as-active',
            str(skill_dir),
        ]
        result = run_in_repo(repo, command, expect=0)
        payload = load_json_output(result, command=command)
        usage = payload.get('exception_usage') or []
        if not any(item.get('id') == 'promotion-trace-waiver' for item in usage):
            fail(f'expected promotion exception usage in JSON output, got {usage!r}')
        trace = payload.get('policy_trace') or {}
        exceptions = trace.get('exceptions') or []
        record = next((item for item in exceptions if item.get('id') == 'promotion-trace-waiver'), None)
        if not record:
            fail(f'expected promotion trace exception entry, got {exceptions!r}')
        if record.get('justification') != 'Trace fixture waiver':
            fail(f'expected trace justification to survive, got {record!r}')
        if record.get('expires_at') != '2099-01-01T00:00:00Z':
            fail(f'expected trace expires_at to survive, got {record!r}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_release_policy_trace():
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check-release-state.py'),
        str(ACTIVE_SKILL),
        '--json',
    ]
    result = run(command)
    payload = load_json_output(result, command=command)
    trace = payload.get('policy_trace') or {}
    if trace.get('domain') != 'release_policy':
        fail(f"expected release_policy trace, got {trace.get('domain')!r}")
    for key in ['decision', 'reasons', 'blocking_rules', 'effective_sources']:
        if key not in trace:
            fail(f'missing release policy trace field {key!r}')


def scenario_validation_policy_traces():
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'validate-registry.py'),
        '--json',
    ]
    result = run(command)
    payload = load_json_output(result, command=command)
    traces = payload.get('policy_traces')
    if not isinstance(traces, list) or not traces:
        fail(f'expected non-empty policy_traces list, got {traces!r}')
    if not any(trace.get('domain') == 'namespace_policy' for trace in traces if isinstance(trace, dict)):
        fail(f'expected at least one namespace_policy trace, got {traces!r}')


def scenario_validation_errors_are_structured():
    tmpdir, repo = copy_repo()
    try:
        skill_dir = repo / 'skills' / 'active' / 'operate-infinitas-skill'
        meta_path = skill_dir / '_meta.json'
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta.pop('owner', None)
        write_json(meta_path, meta)

        command = [
            sys.executable,
            str(repo / 'scripts' / 'validate-registry.py'),
            '--json',
            str(skill_dir),
        ]
        result = run_in_repo(repo, command, expect=1)
        payload = load_json_output(result, command=command)
        validation_errors = payload.get('validation_errors')
        if not isinstance(validation_errors, list) or not validation_errors:
            fail(f'expected structured validation_errors list, got {validation_errors!r}')
        skill_rel = str(skill_dir.relative_to(repo))
        entry = next((item for item in validation_errors if item.get('skill_path') == skill_rel), None)
        if not entry:
            fail(f'expected validation_errors entry for {skill_rel!r}, got {validation_errors!r}')
        errors = entry.get('errors') or []
        if not any('owner' in message for message in errors):
            fail(f"expected structured validation error to mention missing owner, got {errors!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    if not ACTIVE_SKILL.is_dir():
        fail(f'missing active skill fixture: {ACTIVE_SKILL}')
    scenario_promotion_policy_trace()
    scenario_promotion_policy_failure_trace()
    scenario_promotion_exception_trace()
    scenario_release_policy_trace()
    scenario_validation_policy_traces()
    scenario_validation_errors_are_structured()
    print('OK: policy evaluation trace checks passed')


if __name__ == '__main__':
    main()
