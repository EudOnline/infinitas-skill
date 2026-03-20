#!/usr/bin/env python3
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        fail(f'could not load module {module_name} from {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-stale-guardrails-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def stale_item():
    return {
        'name': 'demo-skill',
        'integrity': {
            'state': 'verified',
            'last_verified_at': '2026-03-10T00:00:00Z',
        },
        'last_checked_at': '2026-03-10T00:00:00Z',
    }


def legacy_item():
    return {
        'name': 'legacy-skill',
        'integrity': {
            'state': 'unknown',
        },
    }


def main():
    tmpdir, repo = prepare_repo()
    try:
        sys.path.insert(0, str(repo / 'scripts'))
        policy_lib = load_module('install_integrity_policy_lib', repo / 'scripts' / 'install_integrity_policy_lib.py')
        integrity_lib = load_module('installed_integrity_lib', repo / 'scripts' / 'installed_integrity_lib.py')

        default_policy = policy_lib.default_install_integrity_policy()
        freshness = default_policy.get('freshness') or {}
        if freshness.get('stale_policy') != 'warn':
            fail(f"expected default stale_policy 'warn', got {default_policy!r}")

        normalized = policy_lib.normalize_install_integrity_policy(
            {
                '$schema': '../schemas/install-integrity-policy.schema.json',
                'schema_version': 1,
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'warn',
                },
                'history': {
                    'max_inline_events': 5,
                },
            }
        )
        if (normalized.get('freshness') or {}).get('stale_policy') != 'warn':
            fail(f'expected normalized stale_policy to be preserved, got {normalized!r}')

        try:
            policy_lib.normalize_install_integrity_policy(
                {
                    '$schema': '../schemas/install-integrity-policy.schema.json',
                    'schema_version': 1,
                    'freshness': {
                        'stale_after_hours': 24,
                        'stale_policy': 'panic',
                    },
                    'history': {
                        'max_inline_events': 5,
                    },
                }
            )
        except policy_lib.InstallIntegrityPolicyError:
            pass
        else:
            fail('expected invalid stale_policy to raise InstallIntegrityPolicyError')

        decision_fn = getattr(integrity_lib, 'evaluate_installed_freshness_gate', None)
        if not callable(decision_fn):
            fail('missing evaluate_installed_freshness_gate helper')

        ignore_decision = decision_fn(
            stale_item(),
            policy={
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'ignore',
                },
                'history': {
                    'max_inline_events': 5,
                },
            },
            now='2026-03-13T00:00:00Z',
        )
        if ignore_decision.get('freshness_state') != 'stale' or ignore_decision.get('blocking') is not False:
            fail(f'expected ignore policy to allow stale install, got {ignore_decision!r}')
        if ignore_decision.get('warning') not in {None, ''}:
            fail(f'expected ignore policy warning to stay empty, got {ignore_decision!r}')

        warn_decision = decision_fn(
            stale_item(),
            policy={
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'warn',
                },
                'history': {
                    'max_inline_events': 5,
                },
            },
            now='2026-03-13T00:00:00Z',
        )
        if warn_decision.get('freshness_state') != 'stale' or warn_decision.get('blocking') is not False:
            fail(f'expected warn policy to allow stale install with warning, got {warn_decision!r}')
        if 'report-installed-integrity.py' not in (warn_decision.get('warning') or ''):
            fail(f'expected warn policy to recommend refresh command, got {warn_decision!r}')

        fail_decision = decision_fn(
            stale_item(),
            policy={
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'fail',
                },
                'history': {
                    'max_inline_events': 5,
                },
            },
            now='2026-03-13T00:00:00Z',
        )
        if fail_decision.get('freshness_state') != 'stale' or fail_decision.get('blocking') is not True:
            fail(f'expected fail policy to block stale install, got {fail_decision!r}')
        if 'report-installed-integrity.py' not in (fail_decision.get('warning') or ''):
            fail(f'expected fail policy to recommend refresh command, got {fail_decision!r}')

        never_verified_decision = decision_fn(
            legacy_item(),
            policy={
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'fail',
                },
                'history': {
                    'max_inline_events': 5,
                },
            },
            now='2026-03-13T00:00:00Z',
        )
        if never_verified_decision.get('freshness_state') != 'never-verified':
            fail(f"expected never-verified freshness_state, got {never_verified_decision!r}")
        if never_verified_decision.get('blocking') is not False:
            fail(f'expected never-verified entries to remain additive for now, got {never_verified_decision!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: installed integrity stale guardrail checks passed')


if __name__ == '__main__':
    main()
