#!/usr/bin/env python3
"""Guard-rail checks for installed-integrity never-verified policy behaviour.

Imports directly from the infinitas_skill package (post ADR 0001/0002 migration).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


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
    from infinitas_skill.install.integrity_policy import (
        InstallIntegrityPolicyError,
        default_install_integrity_policy,
        normalize_install_integrity_policy,
    )
    from infinitas_skill.install.installed_integrity import (
        evaluate_installed_mutation_readiness,
    )

    default_policy = default_install_integrity_policy()
    freshness = default_policy.get('freshness') or {}
    expected_default = {
        'stale_after_hours': 168,
        'stale_policy': 'warn',
        'never_verified_policy': 'warn',
    }
    if freshness != expected_default:
        fail(f'expected default freshness policy {expected_default!r}, got {freshness!r}')

    normalized = normalize_install_integrity_policy(
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
        normalize_install_integrity_policy(
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
    except InstallIntegrityPolicyError:
        pass
    else:
        fail('expected invalid never_verified_policy to raise InstallIntegrityPolicyError')

    decision_fn = evaluate_installed_mutation_readiness
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

    print('OK: installed integrity never-verified guardrail checks passed')


if __name__ == '__main__':
    main()
