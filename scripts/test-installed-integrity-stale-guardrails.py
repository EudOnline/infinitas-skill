#!/usr/bin/env python3
"""Guard-rail checks for installed-integrity stale-policy behaviour.

Imports directly from the infinitas_skill package (post ADR 0001/0002 migration).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def stale_item():
    return {
        "name": "demo-skill",
        "integrity": {
            "state": "verified",
            "last_verified_at": "2026-03-10T00:00:00Z",
        },
        "last_checked_at": "2026-03-10T00:00:00Z",
    }


def legacy_item():
    return {
        "name": "legacy-skill",
        "integrity": {
            "state": "unknown",
        },
    }


def main():
    from infinitas_skill.install.integrity_policy import (
        InstallIntegrityPolicyError,
        default_install_integrity_policy,
        normalize_install_integrity_policy,
    )
    from infinitas_skill.install.installed_integrity import (
        evaluate_installed_freshness_gate,
    )

    default_policy = default_install_integrity_policy()
    freshness = default_policy.get("freshness") or {}
    if freshness.get("stale_policy") != "warn":
        fail(f"expected default stale_policy 'warn', got {default_policy!r}")

    normalized = normalize_install_integrity_policy(
        {
            "$schema": "../schemas/install-integrity-policy.schema.json",
            "schema_version": 1,
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "warn",
            },
            "history": {
                "max_inline_events": 5,
            },
        }
    )
    if (normalized.get("freshness") or {}).get("stale_policy") != "warn":
        fail(f"expected normalized stale_policy to be preserved, got {normalized!r}")

    try:
        normalize_install_integrity_policy(
            {
                "$schema": "../schemas/install-integrity-policy.schema.json",
                "schema_version": 1,
                "freshness": {
                    "stale_after_hours": 24,
                    "stale_policy": "panic",
                },
                "history": {
                    "max_inline_events": 5,
                },
            }
        )
    except InstallIntegrityPolicyError:
        pass
    else:
        fail("expected invalid stale_policy to raise InstallIntegrityPolicyError")

    decision_fn = evaluate_installed_freshness_gate
    if not callable(decision_fn):
        fail("missing evaluate_installed_freshness_gate helper")

    ignore_decision = decision_fn(
        stale_item(),
        policy={
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "ignore",
            },
            "history": {
                "max_inline_events": 5,
            },
        },
        now="2026-03-13T00:00:00Z",
    )
    if (
        ignore_decision.get("freshness_state") != "stale"
        or ignore_decision.get("blocking") is not False
    ):
        fail(f"expected ignore policy to allow stale install, got {ignore_decision!r}")
    if ignore_decision.get("warning") not in {None, ""}:
        fail(f"expected ignore policy warning to stay empty, got {ignore_decision!r}")

    warn_decision = decision_fn(
        stale_item(),
        policy={
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "warn",
            },
            "history": {
                "max_inline_events": 5,
            },
        },
        now="2026-03-13T00:00:00Z",
    )
    if (
        warn_decision.get("freshness_state") != "stale"
        or warn_decision.get("blocking") is not False
    ):
        fail(f"expected warn policy to allow stale install with warning, got {warn_decision!r}")
    if "report-installed-integrity.py" not in (warn_decision.get("warning") or ""):
        fail(f"expected warn policy to recommend refresh command, got {warn_decision!r}")

    fail_decision = decision_fn(
        stale_item(),
        policy={
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "fail",
            },
            "history": {
                "max_inline_events": 5,
            },
        },
        now="2026-03-13T00:00:00Z",
    )
    if fail_decision.get("freshness_state") != "stale" or fail_decision.get("blocking") is not True:
        fail(f"expected fail policy to block stale install, got {fail_decision!r}")
    if "report-installed-integrity.py" not in (fail_decision.get("warning") or ""):
        fail(f"expected fail policy to recommend refresh command, got {fail_decision!r}")

    never_verified_decision = decision_fn(
        legacy_item(),
        policy={
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "fail",
            },
            "history": {
                "max_inline_events": 5,
            },
        },
        now="2026-03-13T00:00:00Z",
    )
    if never_verified_decision.get("freshness_state") != "never-verified":
        fail(f"expected never-verified freshness_state, got {never_verified_decision!r}")
    if never_verified_decision.get("blocking") is not False:
        fail(
            f"expected never-verified entries to remain additive for now, got {never_verified_decision!r}"
        )

    print("OK: installed integrity stale guardrail checks passed")


if __name__ == "__main__":
    main()
