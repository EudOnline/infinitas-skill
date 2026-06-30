from __future__ import annotations

import pytest

from infinitas_skill.install.installed_integrity import evaluate_installed_freshness_gate
from infinitas_skill.install.integrity_policy import (
    InstallIntegrityPolicyError,
    default_install_integrity_policy,
    normalize_install_integrity_policy,
)


def _stale_item() -> dict:
    return {
        "name": "demo-skill",
        "integrity": {"state": "verified", "last_verified_at": "2026-03-10T00:00:00Z"},
        "last_checked_at": "2026-03-10T00:00:00Z",
    }


def _legacy_item() -> dict:
    return {"name": "legacy-skill", "integrity": {"state": "unknown"}}


def _policy(stale_policy: str) -> dict:
    return {
        "freshness": {"stale_after_hours": 24, "stale_policy": stale_policy},
        "history": {"max_inline_events": 5},
    }


def test_default_stale_policy_is_warn() -> None:
    freshness = (default_install_integrity_policy().get("freshness") or {})
    assert freshness.get("stale_policy") == "warn"


def test_normalize_preserves_stale_policy() -> None:
    normalized = normalize_install_integrity_policy(
        {
            "$schema": "../schemas/install-integrity-policy.schema.json",
            "schema_version": 1,
            "freshness": {"stale_after_hours": 24, "stale_policy": "warn"},
            "history": {"max_inline_events": 5},
        }
    )
    assert (normalized.get("freshness") or {}).get("stale_policy") == "warn"


def test_invalid_stale_policy_raises() -> None:
    with pytest.raises(InstallIntegrityPolicyError):
        normalize_install_integrity_policy(
            {
                "$schema": "../schemas/install-integrity-policy.schema.json",
                "schema_version": 1,
                "freshness": {"stale_after_hours": 24, "stale_policy": "panic"},
                "history": {"max_inline_events": 5},
            }
        )


@pytest.mark.parametrize(
    "stale_policy,blocking,expects_warning",
    [("ignore", False, False), ("warn", False, True), ("fail", True, True)],
)
def test_stale_freshness_gate(
    stale_policy: str, blocking: bool, expects_warning: bool
) -> None:
    decision = evaluate_installed_freshness_gate(
        _stale_item(), policy=_policy(stale_policy), now="2026-03-13T00:00:00Z"
    )
    assert decision["freshness_state"] == "stale"
    assert decision["blocking"] is blocking
    warning = decision.get("warning") or ""
    if expects_warning:
        assert "report-installed-integrity.py" in warning
    else:
        assert warning == ""


def test_never_verified_legacy_entry_remains_additive() -> None:
    decision = evaluate_installed_freshness_gate(
        _legacy_item(), policy=_policy("fail"), now="2026-03-13T00:00:00Z"
    )
    assert decision["freshness_state"] == "never-verified"
    assert decision["blocking"] is False
