"""Freshness and mutation-readiness projections for installed skills."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infinitas_skill.install.installed_integrity_core import (
    default_integrity_freshness,
    normalize_integrity_capability_fields,
    normalize_integrity_events,
    normalize_integrity_record,
    normalize_timestamp_string,
    parse_timestamp,
)
from infinitas_skill.install.integrity_policy import default_install_integrity_policy


def build_integrity_freshness(
    item: dict[str, Any] | None,
    *,
    policy: dict[str, Any] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    current = item or {}
    resolved_policy = policy or default_install_integrity_policy()
    normalized = default_integrity_freshness()
    integrity = normalize_integrity_record(current.get("integrity"))
    last_checked_at = normalize_timestamp_string(current.get("last_checked_at"))
    checked_at = last_checked_at or integrity.get("last_verified_at")
    checked_at_dt = parse_timestamp(checked_at)
    if checked_at_dt is None:
        return normalized
    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif isinstance(now, datetime):
        now_dt = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    else:
        now_dt = parse_timestamp(now) or datetime.now(timezone.utc)
    freshness_policy = resolved_policy.get("freshness") or {}
    stale_after_hours = freshness_policy.get("stale_after_hours")
    if not isinstance(stale_after_hours, (int, float)):
        stale_after_hours = default_install_integrity_policy()["freshness"]["stale_after_hours"]
    age_seconds = max(0, int((now_dt - checked_at_dt).total_seconds()))
    normalized["freshness_state"] = "stale" if age_seconds > (stale_after_hours * 3600) else "fresh"
    normalized["checked_age_seconds"] = age_seconds
    normalized["last_checked_at"] = last_checked_at
    return normalized


def _policy_choice(policy: dict[str, Any], key: str) -> str:
    freshness_policy = policy.get("freshness") or {}
    default_freshness = default_install_integrity_policy()["freshness"]
    return str(freshness_policy.get(key) or default_freshness[key])


def _warning_for_recovery_action(recovery_action: str) -> str | None:
    warnings = {
        "refresh": (
            "run infinitas install report <target-dir> --refresh before overwriting local files"
        ),
        "repair": (
            "run infinitas install verify <skill> <target-dir> --json or infinitas install repair "
            "<skill> <target-dir> before overwriting local files"
        ),
        "backfill-distribution-manifest": (
            "backfill the signed distribution manifest or reinstall the skill "
            "from a trusted immutable source before overwriting local files"
        ),
        "reinstall": (
            "reinstall the skill from a trusted immutable source before overwriting local files"
        ),
    }
    return warnings.get(recovery_action)


def recovery_action_for_integrity(
    integrity_record: object,
    *,
    capability: str = "unknown",
    reason: str | None = None,
    freshness_state: str = "never-verified",
) -> str:
    state = normalize_integrity_record(integrity_record).get("state")
    if state == "drifted":
        return "repair"
    if freshness_state == "stale":
        return "refresh"
    if freshness_state == "never-verified":
        if capability == "supported":
            return "refresh"
        return (
            "backfill-distribution-manifest"
            if reason == "missing-signed-file-manifest"
            else "reinstall"
        )
    if capability == "unknown" and reason == "missing-signed-file-manifest":
        return "backfill-distribution-manifest"
    return "none" if state == "verified" else "reinstall"


def evaluate_installed_mutation_readiness(
    item: dict[str, Any] | None,
    *,
    policy: dict[str, Any] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    current = item or {}
    resolved_policy = policy or default_install_integrity_policy()
    integrity = normalize_integrity_record(current.get("integrity"))
    capability = normalize_integrity_capability_fields(
        current.get("integrity_capability"), current.get("integrity_reason")
    )
    freshness = build_integrity_freshness(current, policy=resolved_policy, now=now)
    freshness_state = freshness.get("freshness_state")
    recovery_action = recovery_action_for_integrity(
        integrity,
        capability=str(capability.get("integrity_capability")),
        reason=capability.get("integrity_reason"),
        freshness_state=str(freshness_state),
    )
    readiness, mutation_policy, reason_code = "ready", None, None
    if integrity.get("state") == "drifted":
        readiness, reason_code, recovery_action = "blocked", "drifted-installed-skill", "repair"
    elif freshness_state in {"stale", "never-verified"}:
        policy_key = "stale_policy" if freshness_state == "stale" else "never_verified_policy"
        mutation_policy = _policy_choice(resolved_policy, policy_key)
        readiness = {"ignore": "ready", "warn": "warning", "fail": "blocked"}[mutation_policy]
        if readiness != "ready":
            reason_code = f"{freshness_state}-installed-integrity"
    warning = _warning_for_recovery_action(recovery_action) if readiness != "ready" else None
    return {
        "freshness_state": freshness_state,
        "checked_age_seconds": freshness.get("checked_age_seconds"),
        "last_checked_at": freshness.get("last_checked_at"),
        "freshness_policy": mutation_policy
        if freshness_state in {"stale", "never-verified"}
        else None,
        "stale": freshness_state == "stale",
        "blocking": readiness == "blocked",
        "warning": warning,
        "mutation_readiness": readiness,
        "mutation_policy": mutation_policy,
        "mutation_reason_code": reason_code,
        "recovery_action": recovery_action,
    }


def evaluate_installed_freshness_gate(
    item: dict[str, Any] | None,
    *,
    policy: dict[str, Any] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    readiness = evaluate_installed_mutation_readiness(item, policy=policy, now=now)
    return {
        "freshness_state": readiness.get("freshness_state"),
        "checked_age_seconds": readiness.get("checked_age_seconds"),
        "last_checked_at": readiness.get("last_checked_at"),
        "freshness_policy": readiness.get("freshness_policy"),
        "stale": readiness.get("stale"),
        "blocking": readiness.get("blocking"),
        "reason_code": readiness.get("mutation_reason_code"),
        "warning": readiness.get("warning"),
    }


def build_installed_integrity_report_item(
    name: str,
    item: dict[str, Any] | None,
    *,
    policy: dict[str, Any] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    current = item or {}
    integrity = normalize_integrity_record(current.get("integrity"))
    capability = normalize_integrity_capability_fields(
        current.get("integrity_capability"), current.get("integrity_reason")
    )
    readiness = evaluate_installed_mutation_readiness(current, policy=policy, now=now)
    return {
        "name": current.get("name") or name,
        "qualified_name": current.get("source_qualified_name")
        or current.get("qualified_name")
        or current.get("name")
        or name,
        "installed_version": current.get("installed_version") or current.get("version"),
        "integrity": integrity,
        "integrity_capability": capability.get("integrity_capability"),
        "integrity_reason": capability.get("integrity_reason"),
        "last_verified_at": integrity.get("last_verified_at"),
        "freshness_state": readiness.get("freshness_state"),
        "checked_age_seconds": readiness.get("checked_age_seconds"),
        "last_checked_at": readiness.get("last_checked_at"),
        "freshness_policy": readiness.get("freshness_policy"),
        "freshness_warning": readiness.get("warning"),
        "mutation_readiness": readiness.get("mutation_readiness"),
        "mutation_policy": readiness.get("mutation_policy"),
        "mutation_reason_code": readiness.get("mutation_reason_code"),
        "recovery_action": readiness.get("recovery_action"),
        "recommended_action": recovery_action_for_integrity(
            integrity,
            capability=str(capability.get("integrity_capability")),
            reason=capability.get("integrity_reason"),
            freshness_state=str(readiness.get("freshness_state")),
        ),
        "integrity_events": normalize_integrity_events(current.get("integrity_events")),
    }
