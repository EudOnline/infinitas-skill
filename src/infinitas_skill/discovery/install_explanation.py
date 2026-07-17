from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _dedupe_strings(values: Iterable[object] | None) -> list[str]:
    seen = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _listify(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _coalesce_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_resolve_explanation(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    raw_resolved = payload.get("resolved")
    resolved = raw_resolved if isinstance(raw_resolved, dict) else {}
    state = payload.get("state") or "unknown"
    registry_name = _coalesce_string(resolved.get("source_registry"))
    version = _coalesce_string(resolved.get("resolved_version"))
    reasons = []

    if state == "resolved-private":
        selection_reason = (
            "selected the default-registry match because it outranks external candidates"
        )
        reasons.append("default registry matches win before external registries")
    elif state == "resolved-external":
        selection_reason = (
            "selected the external match because no default-registry candidate resolved"
        )
        reasons.append("external registry installs require confirmation before materialization")
    elif state == "ambiguous":
        selection_reason = "found multiple matching skills, so no single winner was chosen"
        reasons.append("use a qualified_name to disambiguate matching candidates")
    elif state == "incompatible":
        selection_reason = (
            "matched skills existed, but none satisfied the requested compatibility filters"
        )
        reasons.append(
            "agent compatibility blocks automatic selection when no compatible match exists"
        )
    elif state == "not-found":
        selection_reason = "no discovery-index candidate matched the requested name"
        reasons.append("search again or use a qualified_name present in discovery-index.json")
    else:
        selection_reason = "resolution did not finish with a usable candidate"
        reasons.append("inspect the resolver output and discovery catalogs before retrying")

    if version:
        version_reason = f"selected version {version} from the discovery result"
    else:
        version_reason = "no version was selected during resolution"

    next_actions = _dedupe_strings(
        [
            payload.get("recommended_next_step"),
            "run infinitas discovery inspect for release details" if resolved else None,
        ]
    )

    return {
        "selection_reason": selection_reason,
        "registry_used": registry_name,
        "confirmation_required": bool(payload.get("requires_confirmation")),
        "version_reason": version_reason,
        "policy_reasons": reasons,
        "next_actions": next_actions,
    }


def build_install_explanation(
    resolve_payload: dict[str, Any] | None,
    payload: dict[str, Any] | None = None,
    *,
    requested_version: str | None = None,
) -> dict[str, Any]:
    resolve_payload = resolve_payload if isinstance(resolve_payload, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    raw_resolved = resolve_payload.get("resolved")
    resolved = raw_resolved if isinstance(raw_resolved, dict) else {}
    resolved_version = _coalesce_string(
        payload.get("resolved_version"),
        requested_version,
        resolved.get("resolved_version"),
    )
    base = build_resolve_explanation(resolve_payload)
    reasons = _dedupe_strings(
        _listify(base.get("policy_reasons"))
        + _listify((payload.get("explanation") or {}).get("policy_reasons"))
    )

    if payload.get("state") == "installed":
        selection_reason = "installed the resolver winner using immutable registry artifacts"
    elif payload.get("state") == "planned":
        selection_reason = (
            "prepared an install plan for the resolver winner without materializing files"
        )
    elif payload.get("error_code") == "confirmation-required":
        selection_reason = (
            "blocked auto-install because the selected registry requires confirmation"
        )
    elif payload.get("error_code") == "ambiguous-skill-name":
        selection_reason = "blocked install because the requested name matched multiple skills"
    elif payload.get("error_code") == "incompatible-target-agent":
        selection_reason = (
            "blocked install because no compatible candidate matched the requested target agent"
        )
    elif payload.get("error_code") == "skill-not-found":
        selection_reason = "blocked install because discovery found no matching skill"
    elif payload.get("error_code") == "resolver-failed":
        selection_reason = (
            "blocked install because skill resolution failed before a candidate was selected"
        )
    else:
        selection_reason = str(base.get("selection_reason") or "evaluated install resolution")

    version_reason = (
        f"using resolved version {resolved_version} for install"
        if resolved_version
        else base.get("version_reason")
    )
    next_actions = _dedupe_strings(
        _listify((payload.get("explanation") or {}).get("next_actions"))
        + _listify(base.get("next_actions"))
        + [payload.get("suggested_action"), payload.get("next_step")]
    )
    return {
        "selection_reason": selection_reason,
        "registry_used": _coalesce_string(
            payload.get("source_registry"),
            resolved.get("source_registry"),
            base.get("registry_used"),
        ),
        "confirmation_required": bool(
            payload.get("requires_confirmation")
            if "requires_confirmation" in payload
            else resolve_payload.get("requires_confirmation")
        ),
        "version_reason": version_reason,
        "policy_reasons": reasons,
        "next_actions": next_actions,
    }


def build_update_explanation(
    info: dict[str, Any] | None, payload: dict[str, Any] | None
) -> dict[str, Any]:
    info = info if isinstance(info, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    installed = _coalesce_string(info.get("installed_version"), payload.get("installed_version"))
    latest = _coalesce_string(payload.get("latest_available_version"))
    if payload.get("update_available"):
        selection_reason = "found a newer released version in the installed source registry"
    else:
        selection_reason = "the installed version already matches the newest released version"
    version_reason = (
        "installed version "
        f"{installed}; latest available version {latest or installed or 'unknown'}"
    )
    reasons = ["update checks stay pinned to the installed source registry"]
    if payload.get("mutation_reason_code") == "drifted-installed-skill":
        reasons.append(
            "local installed files have drifted from the recorded immutable release, "
            "so repair is required before overwrite-style mutation"
        )
    elif payload.get("freshness_state") == "stale":
        reasons.append(
            "local installed-integrity freshness is stale, so refresh is recommended "
            "before overwrite-style mutation"
        )
    elif payload.get("mutation_reason_code") == "never-verified-installed-integrity":
        recovery_action = payload.get("recovery_action")
        if recovery_action == "refresh":
            reasons.append(
                "local installed-integrity is never-verified for this copy, so "
                "refresh is recommended before overwrite-style mutation"
            )
        elif recovery_action == "backfill-distribution-manifest":
            reasons.append(
                "local installed-integrity is never-verified and the release is "
                "missing a signed distribution manifest, so backfill is required "
                "before overwrite-style mutation"
            )
        else:
            reasons.append(
                "local installed-integrity is never-verified for this copy, so "
                "reinstall is recommended before overwrite-style mutation"
            )
    next_actions = _dedupe_strings([payload.get("next_step")])
    freshness_warning = payload.get("freshness_warning")
    if isinstance(freshness_warning, str) and freshness_warning.strip():
        next_actions.append(freshness_warning)
    return {
        "selection_reason": selection_reason,
        "registry_used": _coalesce_string(
            payload.get("source_registry"), info.get("source_registry")
        ),
        "confirmation_required": False,
        "version_reason": version_reason,
        "policy_reasons": reasons,
        "next_actions": next_actions,
    }


def _blocked_never_verified_reason(recovery_action: object) -> str:
    if recovery_action == "refresh":
        return (
            "refresh local installed-integrity before planning or applying an "
            "overwrite-style upgrade because the installed copy is never-verified"
        )
    if recovery_action == "backfill-distribution-manifest":
        return (
            "backfill the signed distribution manifest before planning or applying an "
            "overwrite-style upgrade because the installed copy is never-verified"
        )
    return (
        "reinstall the skill from a trusted immutable source before planning or applying an "
        "overwrite-style upgrade because the installed copy is never-verified"
    )


def _planned_never_verified_reason(recovery_action: object) -> str:
    if recovery_action == "refresh":
        return (
            "the installed copy is never-verified, so refresh is recommended before applying "
            "the upgrade"
        )
    if recovery_action == "backfill-distribution-manifest":
        return (
            "the installed copy is never-verified and still needs signed distribution manifest "
            "support before applying the upgrade"
        )
    return (
        "the installed copy is never-verified, so reinstall is recommended before applying "
        "the upgrade"
    )


def _current_never_verified_reason(recovery_action: object) -> str:
    action = "reinstall"
    if recovery_action == "refresh":
        action = "refresh"
    elif recovery_action == "backfill-distribution-manifest":
        action = "backfill"
    return (
        "no files would be overwritten for this request, but "
        f"{action} is still recommended because the installed copy is never-verified"
    )


def _upgrade_selection(payload: dict[str, Any], reasons: list[str]) -> str:
    state = payload.get("state") or "unknown"
    recovery_action = payload.get("recovery_action")
    error_code = payload.get("error_code")
    if error_code == "cross-source-upgrade-not-allowed":
        return "blocked the requested registry override for the installed skill"
    if error_code == "stale-installed-integrity":
        reasons.append(
            "refresh local installed-integrity before planning or applying an "
            "overwrite-style upgrade"
        )
        return "blocked the requested upgrade because the recorded local verification is stale"
    if error_code == "never-verified-installed-integrity":
        reasons.append(_blocked_never_verified_reason(recovery_action))
        return "blocked the requested upgrade because the installed copy is still never-verified"
    if state == "planned":
        reasons.append("confirm mode previews the upgrade path before switching installed files")
        if payload.get("freshness_state") == "stale":
            reasons.append(
                "the installed copy is stale, so refresh is recommended before applying the upgrade"
            )
        elif payload.get("mutation_reason_code") == "never-verified-installed-integrity":
            reasons.append(_planned_never_verified_reason(recovery_action))
        return "prepared a same-registry upgrade plan without materializing files"
    if state == "installed":
        return "upgraded the installed skill in place from the same registry"
    if state == "up-to-date":
        if payload.get("mutation_reason_code") == "stale-installed-integrity":
            reasons.append(
                "no files would be overwritten for this request, but the recorded "
                "local verification is stale"
            )
        elif payload.get("mutation_reason_code") == "never-verified-installed-integrity":
            reasons.append(_current_never_verified_reason(recovery_action))
        return "no upgrade was needed because the installed version is already current"
    return "evaluated the upgrade request against the installed registry source"


def build_upgrade_explanation(
    info: dict[str, Any] | None, payload: dict[str, Any] | None
) -> dict[str, Any]:
    info = info if isinstance(info, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    from_version = _coalesce_string(payload.get("from_version"), info.get("installed_version"))
    to_version = _coalesce_string(payload.get("to_version"), from_version)
    reasons = ["cross-source upgrades are blocked to preserve source provenance"]
    selection_reason = _upgrade_selection(payload, reasons)

    version_reason = f"upgrade path is {from_version or 'unknown'} -> {to_version or 'unknown'}"
    next_actions = _dedupe_strings([payload.get("next_step")])
    freshness_warning = payload.get("freshness_warning")
    if isinstance(freshness_warning, str) and freshness_warning.strip():
        next_actions.append(freshness_warning)
    return {
        "selection_reason": selection_reason,
        "registry_used": _coalesce_string(
            payload.get("source_registry"), info.get("source_registry")
        ),
        "confirmation_required": False,
        "version_reason": version_reason,
        "policy_reasons": reasons,
        "next_actions": next_actions,
    }
