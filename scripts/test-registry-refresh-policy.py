#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from registry_source_lib import validate_registry_config

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def load_base_config():
    return json.loads((ROOT / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))


def remote_registry_template():
    config = load_base_config()
    config['default_registry'] = 'upstream'
    config['registries'] = [
        {
            'name': 'upstream',
            'kind': 'git',
            'url': 'https://github.com/example/upstream-skills.git',
            'priority': 90,
            'enabled': True,
            'trust': 'trusted',
            'allowed_hosts': ['github.com'],
            'allowed_refs': ['refs/tags/v1.2.3'],
            'pin': {'mode': 'tag', 'value': 'v1.2.3'},
            'update_policy': {'mode': 'pinned'},
        }
    ]
    return config


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def copy_repo(tmpdir: Path):
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '.worktrees', '.cache', '__pycache__', 'scripts/__pycache__'),
    )
    return repo


def create_remote_registry_fixture(tmpdir: Path):
    remote = tmpdir / 'remote.git'
    remote_work = tmpdir / 'remote-work'
    remote_work.mkdir(parents=True, exist_ok=True)
    run(['git', 'init', '-b', 'main'], cwd=remote_work)
    run(['git', 'config', 'user.name', 'Infinitas Test'], cwd=remote_work)
    run(['git', 'config', 'user.email', 'tests@example.com'], cwd=remote_work)
    write_json(
        remote_work / 'skills' / 'active' / 'demo' / '_meta.json',
        {
            'name': 'demo',
            'version': '1.0.0',
            'status': 'active',
            'summary': 'Refresh-policy test fixture skill',
            'distribution': {
                'installable': True,
            },
        },
    )
    run(['git', 'add', '.'], cwd=remote_work)
    run(['git', 'commit', '-m', 'fixture'], cwd=remote_work)
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=remote_work).stdout.strip()
    run(['git', 'tag', 'v1.0.0'], cwd=remote_work)
    run(['git', 'init', '--bare', str(remote)], cwd=tmpdir)
    run(['git', 'remote', 'add', 'origin', str(remote)], cwd=remote_work)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/main'], cwd=remote_work)
    run(['git', 'push', 'origin', 'refs/tags/v1.0.0'], cwd=remote_work)
    return remote, commit


def registry_config_with_remote(remote_url: str):
    config = load_base_config()
    config['default_registry'] = 'upstream'
    config['registries'] = [
        config['registries'][0],
        {
            'name': 'upstream',
            'kind': 'git',
            'url': remote_url,
            'priority': 90,
            'enabled': True,
            'trust': 'trusted',
            'allowed_refs': ['refs/tags/v1.0.0'],
            'pin': {'mode': 'tag', 'value': 'v1.0.0'},
            'update_policy': {'mode': 'pinned'},
            'refresh_policy': {
                'interval_hours': 24,
                'max_cache_age_hours': 72,
                'stale_policy': 'warn',
            },
        },
    ]
    return config


def expect_no_errors(config, root):
    errors = validate_registry_config(root, config)
    if errors:
        fail(f'expected no validation errors, got {errors!r}')


def expect_error(config, root, needle):
    errors = validate_registry_config(root, config)
    if not any(needle in error for error in errors):
        fail(f'expected validation error containing {needle!r}, got {errors!r}')


def scenario_valid_refresh_policy_is_allowed():
    config = remote_registry_template()
    config['registries'][0]['refresh_policy'] = {
        'interval_hours': 24,
        'max_cache_age_hours': 72,
        'stale_policy': 'warn',
    }
    expect_no_errors(config, ROOT)


def scenario_interval_hours_must_be_positive():
    config = remote_registry_template()
    config['registries'][0]['refresh_policy'] = {
        'interval_hours': 0,
        'max_cache_age_hours': 72,
        'stale_policy': 'warn',
    }
    expect_error(config, ROOT, 'refresh_policy.interval_hours')


def scenario_max_cache_age_must_cover_interval():
    config = remote_registry_template()
    config['registries'][0]['refresh_policy'] = {
        'interval_hours': 24,
        'max_cache_age_hours': 12,
        'stale_policy': 'warn',
    }
    expect_error(config, ROOT, 'refresh_policy.max_cache_age_hours')


def scenario_stale_policy_must_be_known():
    config = remote_registry_template()
    config['registries'][0]['refresh_policy'] = {
        'interval_hours': 24,
        'max_cache_age_hours': 72,
        'stale_policy': 'panic',
    }
    expect_error(config, ROOT, 'refresh_policy.stale_policy')


def scenario_local_only_registry_may_omit_refresh_policy():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-refresh-policy-test-'))
    try:
        repo = copy_repo(tmpdir)
        config = json.loads((repo / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))
        expect_no_errors(config, repo)
    finally:
        shutil.rmtree(tmpdir)


def scenario_sync_writes_refresh_state_and_status():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-refresh-policy-sync-test-'))
    try:
        repo = copy_repo(tmpdir)
        remote, expected_commit = create_remote_registry_fixture(tmpdir)
        write_json(repo / 'config' / 'registry-sources.json', registry_config_with_remote(str(remote)))

        run(['bash', 'scripts/sync-registry-source.sh', 'upstream'], cwd=repo)

        state_path = repo / '.cache' / 'registries' / '_state' / 'upstream.json'
        if not state_path.exists():
            fail(f'expected refresh state file to exist at {state_path}')
        payload = json.loads(state_path.read_text(encoding='utf-8'))
        if payload.get('registry') != 'upstream':
            fail(f"expected state registry 'upstream', got {payload!r}")
        if payload.get('kind') != 'git':
            fail(f"expected state kind 'git', got {payload!r}")
        if payload.get('source_commit') != expected_commit:
            fail(f'expected source_commit {expected_commit!r}, got {payload!r}')
        if payload.get('source_tag') != 'v1.0.0':
            fail(f"expected source_tag 'v1.0.0', got {payload!r}")
        if payload.get('source_ref') != 'refs/tags/v1.0.0':
            fail(f"expected source_ref 'refs/tags/v1.0.0', got {payload!r}")
        if payload.get('cache_path') != str((repo / '.cache' / 'registries' / 'upstream').resolve()):
            fail(f'expected cache_path to point at the upstream cache, got {payload!r}')
        if not isinstance(payload.get('refreshed_at'), str) or not payload.get('refreshed_at'):
            fail(f'expected refreshed_at timestamp, got {payload!r}')

        result = run(['python3', 'scripts/registry-refresh-status.py', 'upstream', '--json'], cwd=repo)
        status_payload = json.loads(result.stdout)
        if status_payload.get('registry') != 'upstream':
            fail(f"expected status registry 'upstream', got {status_payload!r}")
        if status_payload.get('freshness_state') != 'fresh':
            fail(f"expected freshness_state 'fresh', got {status_payload!r}")
        if status_payload.get('source_commit') != expected_commit:
            fail(f'expected source_commit {expected_commit!r}, got {status_payload!r}')
        if status_payload.get('refresh_interval_hours') != 24:
            fail(f'expected refresh_interval_hours 24, got {status_payload!r}')
        if status_payload.get('max_cache_age_hours') != 72:
            fail(f'expected max_cache_age_hours 72, got {status_payload!r}')
        if status_payload.get('stale_policy') != 'warn':
            fail(f"expected stale_policy 'warn', got {status_payload!r}")
        if status_payload.get('has_state') is not True:
            fail(f'expected has_state true, got {status_payload!r}')
        age_hours = status_payload.get('age_hours')
        if not isinstance(age_hours, (int, float)) or age_hours < 0:
            fail(f'expected a non-negative age_hours, got {status_payload!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_status_handles_local_only_registry_without_state():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-refresh-policy-status-test-'))
    try:
        repo = copy_repo(tmpdir)
        result = run(['python3', 'scripts/registry-refresh-status.py', 'self', '--json'], cwd=repo)
        payload = json.loads(result.stdout)
        if payload.get('registry') != 'self':
            fail(f"expected status registry 'self', got {payload!r}")
        if payload.get('has_state') is not False:
            fail(f'expected has_state false for local-only registry without state, got {payload!r}')
        if payload.get('freshness_state') != 'not-configured':
            fail(f"expected freshness_state 'not-configured', got {payload!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_valid_refresh_policy_is_allowed()
    scenario_interval_hours_must_be_positive()
    scenario_max_cache_age_must_cover_interval()
    scenario_stale_policy_must_be_known()
    scenario_local_only_registry_may_omit_refresh_policy()
    scenario_sync_writes_refresh_state_and_status()
    scenario_status_handles_local_only_registry_without_state()
    print('OK: registry refresh policy checks passed')


if __name__ == '__main__':
    main()
