from __future__ import annotations

import pytest

from infinitas_skill.install.installed_integrity import evaluate_installed_mutation_readiness
from infinitas_skill.install.integrity_policy import (
    InstallIntegrityPolicyError,
    default_install_integrity_policy,
    normalize_install_integrity_policy,
)


def _refreshable_never_verified_item() -> dict:
    return {
        "name": "demo-skill",
        "integrity": {"state": "verified"},
        "source_distribution_manifest": (
            "catalog/distributions/_legacy/demo-skill/1.2.3/manifest.json"
        ),
        "source_attestation_path": "catalog/provenance/demo-skill-1.2.3.json",
        "integrity_capability": "supported",
    }


def _legacy_never_verified_item() -> dict:
    return {"name": "legacy-skill", "integrity": {"state": "unknown"}}


def _stale_item() -> dict:
    return {
        "name": "stale-skill",
        "integrity": {"state": "verified", "last_verified_at": "2026-03-10T00:00:00Z"},
        "last_checked_at": "2026-03-10T00:00:00Z",
        "source_distribution_manifest": (
            "catalog/distributions/_legacy/stale-skill/1.2.3/manifest.json"
        ),
        "source_attestation_path": "catalog/provenance/stale-skill-1.2.3.json",
        "integrity_capability": "supported",
    }


def _policy_with(*, stale_policy: str = "warn", never_verified_policy: str = "warn") -> dict:
    return {
        "freshness": {
            "stale_after_hours": 24,
            "stale_policy": stale_policy,
            "never_verified_policy": never_verified_policy,
        },
        "history": {"max_inline_events": 5},
    }


def test_default_freshness_policy() -> None:
    freshness = default_install_integrity_policy().get("freshness") or {}
    assert freshness == {
        "stale_after_hours": 168,
        "stale_policy": "warn",
        "never_verified_policy": "warn",
    }


def test_normalize_preserves_never_verified_policy() -> None:
    normalized = normalize_install_integrity_policy(
        {
            "$schema": "../schemas/install-integrity-policy.schema.json",
            "schema_version": 1,
            "freshness": {
                "stale_after_hours": 24,
                "stale_policy": "warn",
                "never_verified_policy": "warn",
            },
            "history": {"max_inline_events": 5},
        }
    )
    assert (normalized.get("freshness") or {}).get("never_verified_policy") == "warn"


def test_invalid_never_verified_policy_raises() -> None:
    with pytest.raises(InstallIntegrityPolicyError):
        normalize_install_integrity_policy(
            {
                "$schema": "../schemas/install-integrity-policy.schema.json",
                "schema_version": 1,
                "freshness": {
                    "stale_after_hours": 24,
                    "stale_policy": "warn",
                    "never_verified_policy": "panic",
                },
                "history": {"max_inline_events": 5},
            }
        )


@pytest.mark.parametrize(
    "policy,readiness,blocking,reason_code",
    [
        ("ignore", "ready", False, None),
        ("warn", "warning", False, "never-verified-installed-integrity"),
        ("fail", "blocked", True, "never-verified-installed-integrity"),
    ],
)
def test_refreshable_never_verified_mutation_readiness(
    policy: str, readiness: str, blocking: bool, reason_code: str | None
) -> None:
    decision = evaluate_installed_mutation_readiness(
        _refreshable_never_verified_item(),
        policy=_policy_with(never_verified_policy=policy),
        now="2026-03-13T00:00:00Z",
    )
    assert decision["freshness_state"] == "never-verified"
    assert decision["mutation_readiness"] == readiness
    assert decision["mutation_policy"] == policy
    assert decision["blocking"] is blocking
    assert decision["mutation_reason_code"] == reason_code
    assert decision["recovery_action"] == "refresh"
    warning = decision.get("warning") or ""
    if reason_code is None:
        assert warning == ""
    else:
        assert "report-installed-integrity.py" in warning
        assert "--refresh" in warning


@pytest.mark.parametrize(
    "policy,readiness,blocking,reason_code",
    [
        ("ignore", "ready", False, None),
        ("warn", "warning", False, "never-verified-installed-integrity"),
        ("fail", "blocked", True, "never-verified-installed-integrity"),
    ],
)
def test_legacy_never_verified_mutation_readiness(
    policy: str, readiness: str, blocking: bool, reason_code: str | None
) -> None:
    decision = evaluate_installed_mutation_readiness(
        _legacy_never_verified_item(),
        policy=_policy_with(never_verified_policy=policy),
        now="2026-03-13T00:00:00Z",
    )
    assert decision["freshness_state"] == "never-verified"
    assert decision["mutation_readiness"] == readiness
    assert decision["mutation_policy"] == policy
    assert decision["blocking"] is blocking
    assert decision["mutation_reason_code"] == reason_code
    assert decision["recovery_action"] == "reinstall"


def test_stale_decision_stays_distinct_from_never_verified() -> None:
    decision = evaluate_installed_mutation_readiness(
        _stale_item(),
        policy=_policy_with(stale_policy="fail", never_verified_policy="fail"),
        now="2026-03-13T00:00:00Z",
    )
    assert decision["freshness_state"] == "stale"
    assert decision["mutation_reason_code"] != "never-verified-installed-integrity"
