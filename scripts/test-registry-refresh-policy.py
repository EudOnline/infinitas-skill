#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

from registry_source_lib import validate_registry_config

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


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
        repo = tmpdir / 'repo'
        shutil.copytree(
            ROOT,
            repo,
            ignore=shutil.ignore_patterns('.git', '.worktrees', '.cache', '__pycache__', 'scripts/__pycache__'),
        )
        config = json.loads((repo / 'config' / 'registry-sources.json').read_text(encoding='utf-8'))
        expect_no_errors(config, repo)
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_valid_refresh_policy_is_allowed()
    scenario_interval_hours_must_be_positive()
    scenario_max_cache_age_must_cover_interval()
    scenario_stale_policy_must_be_known()
    scenario_local_only_registry_may_omit_refresh_policy()
    print('OK: registry refresh policy checks passed')


if __name__ == '__main__':
    main()
