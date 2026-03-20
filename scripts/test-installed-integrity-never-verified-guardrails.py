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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-never-verified-guardrails-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def stale_item():
    return {
        'name': 'stale-skill',
        'integrity': {
            'state': 'verified',
            'last_verified_at': '2026-03-10T00:00:00Z',
        },
        'last_checked_at': '2026-03-10T00:00:00Z',
        'source_distribution_manifest': 'catalog/distributions/_legacy/stale-skill/1.2.3/manifest.json',
        'source_attestation_path': 'catalog/provenance/stale-skill-1.2.3.json',
        'integrity_capability': 'supported',
    }


def refreshable_never_verified_item():
    return {
        'name': 'demo-skill',
        'integrity': {
            'state': 'verified',
        },
        'source_distribution_manifest': 'catalog/distributions/_legacy/demo-skill/1.2.3/manifest.json',
        'source_attestation_path': 'catalog/provenance/demo-skill-1.2.3.json',
        'integrity_capability': 'supported',
    }


def legacy_never_verified_item():
    return {
        'name': 'legacy-skill',
        'integrity': {
            'state': 'unknown',
        },
    }


def policy_with(*, stale_policy='warn', never_verified_policy='warn'):
    return {
        'freshness': {
            'stale_after_hours': 24,
            'stale_policy': stale_policy,
            'never_verified_policy': never_verified_policy,
        },
        'history': {
            'max_inline_events': 5,
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
        expected_default = {
            'stale_after_hours': 168,
            'stale_policy': 'warn',
            'never_verified_policy': 'warn',
        }
        if freshness != expected_default:
            fail(f'expected default freshness policy {expected_default!r}, got {freshness!r}')

        normalized = policy_lib.normalize_install_integrity_policy(
            {
                '$schema': '../schemas/install-integrity-policy.schema.json',
                'schema_version': 1,
                'freshness': {
                    'stale_after_hours': 24,
                    'stale_policy': 'warn',
                    'never_verified_policy': 'warn',
                },
                'history': {
                    'max_inline_events': 5,
                },
            }
        )
        if (normalized.get('freshness') or {}).get('never_verified_policy') != 'warn':
            fail(f'expected normalized never_verified_policy to be preserved, got {normalized!r}')

        try:
            policy_lib.normalize_install_integrity_policy(
                {
                    '$schema': '../schemas/install-integrity-policy.schema.json',
                    'schema_version': 1,
                    'freshness': {
                        'stale_after_hours': 24,
                        'stale_policy': 'warn',
                        'never_verified_policy': 'panic',
                    },
                    'history': {
                        'max_inline_events': 5,
                    },
                }
            )
        except policy_lib.InstallIntegrityPolicyError:
            pass
        else:
            fail('expected invalid never_verified_policy to raise InstallIntegrityPolicyError')

        decision_fn = getattr(integrity_lib, 'evaluate_installed_mutation_readiness', None)
        if not callable(decision_fn):
            fail('missing evaluate_installed_mutation_readiness helper')

        ignore_decision = decision_fn(
            refreshable_never_verified_item(),
            policy=policy_with(never_verified_policy='ignore'),
            now='2026-03-13T00:00:00Z',
        )
        if ignore_decision.get('freshness_state') != 'never-verified':
            fail(f"expected ignore policy freshness_state 'never-verified', got {ignore_decision!r}")
        if ignore_decision.get('mutation_readiness') != 'ready':
            fail(f"expected ignore policy mutation_readiness 'ready', got {ignore_decision!r}")
        if ignore_decision.get('mutation_policy') != 'ignore':
            fail(f"expected ignore policy mutation_policy 'ignore', got {ignore_decision!r}")
        if ignore_decision.get('blocking') is not False:
            fail(f'expected ignore policy to stay additive, got {ignore_decision!r}')
        if ignore_decision.get('warning') not in {None, ''}:
            fail(f'expected ignore policy warning to stay empty, got {ignore_decision!r}')
        if ignore_decision.get('mutation_reason_code') is not None:
            fail(f'expected ignore policy mutation_reason_code null, got {ignore_decision!r}')
        if ignore_decision.get('recovery_action') != 'refresh':
            fail(f"expected ignore policy recovery_action 'refresh', got {ignore_decision!r}")

        warn_decision = decision_fn(
            refreshable_never_verified_item(),
            policy=policy_with(never_verified_policy='warn'),
            now='2026-03-13T00:00:00Z',
        )
        if warn_decision.get('freshness_state') != 'never-verified':
            fail(f"expected warn policy freshness_state 'never-verified', got {warn_decision!r}")
        if warn_decision.get('mutation_readiness') != 'warning':
            fail(f"expected warn policy mutation_readiness 'warning', got {warn_decision!r}")
        if warn_decision.get('mutation_policy') != 'warn':
            fail(f"expected warn policy mutation_policy 'warn', got {warn_decision!r}")
        if warn_decision.get('blocking') is not False:
            fail(f'expected warn policy to remain non-blocking, got {warn_decision!r}')
        if warn_decision.get('mutation_reason_code') != 'never-verified-installed-integrity':
            fail(f'expected warn policy to surface never-verified reason code, got {warn_decision!r}')
        if 'report-installed-integrity.py' not in (warn_decision.get('warning') or '') or '--refresh' not in (warn_decision.get('warning') or ''):
            fail(f'expected warn policy to recommend refresh command, got {warn_decision!r}')
        if warn_decision.get('recovery_action') != 'refresh':
            fail(f"expected warn policy recovery_action 'refresh', got {warn_decision!r}")

        fail_decision = decision_fn(
            refreshable_never_verified_item(),
            policy=policy_with(never_verified_policy='fail'),
            now='2026-03-13T00:00:00Z',
        )
        if fail_decision.get('freshness_state') != 'never-verified':
            fail(f"expected fail policy freshness_state 'never-verified', got {fail_decision!r}")
        if fail_decision.get('mutation_readiness') != 'blocked':
            fail(f"expected fail policy mutation_readiness 'blocked', got {fail_decision!r}")
        if fail_decision.get('mutation_policy') != 'fail':
            fail(f"expected fail policy mutation_policy 'fail', got {fail_decision!r}")
        if fail_decision.get('blocking') is not True:
            fail(f'expected fail policy to block overwrite-style mutation, got {fail_decision!r}')
        if fail_decision.get('mutation_reason_code') != 'never-verified-installed-integrity':
            fail(f'expected fail policy to surface never-verified reason code, got {fail_decision!r}')
        if 'report-installed-integrity.py' not in (fail_decision.get('warning') or '') or '--refresh' not in (fail_decision.get('warning') or ''):
            fail(f'expected fail policy to recommend refresh command, got {fail_decision!r}')
        if fail_decision.get('recovery_action') != 'refresh':
            fail(f"expected fail policy recovery_action 'refresh', got {fail_decision!r}")

        legacy_warn_decision = decision_fn(
            legacy_never_verified_item(),
            policy=policy_with(never_verified_policy='warn'),
            now='2026-03-13T00:00:00Z',
        )
        if legacy_warn_decision.get('freshness_state') != 'never-verified':
            fail(f"expected legacy warn freshness_state 'never-verified', got {legacy_warn_decision!r}")
        if legacy_warn_decision.get('mutation_readiness') != 'warning':
            fail(f"expected legacy warn mutation_readiness 'warning', got {legacy_warn_decision!r}")
        if legacy_warn_decision.get('recovery_action') != 'reinstall':
            fail(f"expected legacy warn recovery_action 'reinstall', got {legacy_warn_decision!r}")

        legacy_ignore_decision = decision_fn(
            legacy_never_verified_item(),
            policy=policy_with(never_verified_policy='ignore'),
            now='2026-03-13T00:00:00Z',
        )
        if legacy_ignore_decision.get('mutation_readiness') != 'ready':
            fail(f"expected legacy ignore mutation_readiness 'ready', got {legacy_ignore_decision!r}")
        if legacy_ignore_decision.get('mutation_policy') != 'ignore':
            fail(f"expected legacy ignore mutation_policy 'ignore', got {legacy_ignore_decision!r}")
        if legacy_ignore_decision.get('blocking') is not False:
            fail(f'expected legacy ignore policy to stay additive, got {legacy_ignore_decision!r}')
        if legacy_ignore_decision.get('recovery_action') != 'reinstall':
            fail(f"expected legacy ignore recovery_action 'reinstall', got {legacy_ignore_decision!r}")

        legacy_fail_decision = decision_fn(
            legacy_never_verified_item(),
            policy=policy_with(never_verified_policy='fail'),
            now='2026-03-13T00:00:00Z',
        )
        if legacy_fail_decision.get('mutation_readiness') != 'blocked':
            fail(f"expected legacy fail mutation_readiness 'blocked', got {legacy_fail_decision!r}")
        if legacy_fail_decision.get('mutation_policy') != 'fail':
            fail(f"expected legacy fail mutation_policy 'fail', got {legacy_fail_decision!r}")
        if legacy_fail_decision.get('blocking') is not True:
            fail(f'expected legacy fail policy to block overwrite-style mutation, got {legacy_fail_decision!r}')
        if legacy_fail_decision.get('mutation_reason_code') != 'never-verified-installed-integrity':
            fail(f'expected legacy fail policy to surface never-verified reason code, got {legacy_fail_decision!r}')
        if legacy_fail_decision.get('recovery_action') != 'reinstall':
            fail(f"expected legacy fail recovery_action 'reinstall', got {legacy_fail_decision!r}")

        stale_fail_decision = decision_fn(
            stale_item(),
            policy=policy_with(stale_policy='fail', never_verified_policy='fail'),
            now='2026-03-13T00:00:00Z',
        )
        if stale_fail_decision.get('freshness_state') != 'stale':
            fail(f"expected stale decision freshness_state 'stale', got {stale_fail_decision!r}")
        if stale_fail_decision.get('mutation_reason_code') == 'never-verified-installed-integrity':
            fail(f'expected stale decision to remain distinct from never-verified, got {stale_fail_decision!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: installed integrity never-verified guardrail checks passed')


if __name__ == '__main__':
    main()
