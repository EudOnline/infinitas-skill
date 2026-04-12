from __future__ import annotations

from typing import Any

from .decision_metadata import canonical_decision_metadata


def compatibility_summary(verified_support: dict[str, Any]) -> dict[str, str]:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("state"), str)
            and payload.get("state").strip()
        ):
            summary[platform] = payload.get("state")
    return summary


def compatibility_freshness_summary(verified_support: dict[str, Any]) -> dict[str, str]:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("freshness_state"), str)
            and payload.get("freshness_state").strip()
        ):
            summary[platform] = payload.get("freshness_state")
    return summary


def dependency_summary(dependencies: dict[str, Any]) -> dict[str, Any]:
    root = dependencies.get("root") if isinstance(dependencies, dict) else {}
    steps = dependencies.get("steps") if isinstance(dependencies, dict) else []
    registries = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        registry = step.get("registry")
        if isinstance(registry, str) and registry not in registries:
            registries.append(registry)
    return {
        "root_name": (root or {}).get("name"),
        "root_source_type": (root or {}).get("source_type"),
        "step_count": len(steps or []),
        "registries_consulted": registries
        or list((dependencies.get("registries_consulted") or [])),
    }


def derive_trust_state(
    version_entry: dict[str, Any],
    manifest_payload: dict[str, Any],
    provenance_payload: dict[str, Any],
    distribution: dict[str, Any],
) -> str:
    signature_present = bool(
        version_entry.get("attestation_signature_path")
        or ((manifest_payload.get("attestation_bundle") or {}).get("signature_path"))
    )
    attestation_present = bool(
        version_entry.get("attestation_path")
        or ((manifest_payload.get("attestation_bundle") or {}).get("provenance_path"))
    )
    policy = (
        (provenance_payload.get("attestation") or {})
        if isinstance(provenance_payload, dict)
        else {}
    )
    if (
        signature_present
        and policy.get("require_verified_attestation_for_distribution") is not False
    ):
        return "verified"
    if attestation_present:
        return "attested"
    if (
        distribution.get("manifest_path")
        or version_entry.get("distribution_manifest_path")
        or version_entry.get("manifest_path")
    ):
        return "installable"
    return version_entry.get("trust_state") or "unknown"


def _declared_support(skill_entry: dict[str, Any]) -> list[str]:
    compatibility = skill_entry.get("compatibility") if isinstance(skill_entry, dict) else {}
    declared = (
        (compatibility.get("declared_support") if isinstance(compatibility, dict) else None)
        or skill_entry.get("declared_support")
        or skill_entry.get("agent_compatible")
        or []
    )
    return [item for item in declared if isinstance(item, str) and item]


def _resolved_verified_support(
    skill_entry: dict[str, Any], verified_support: dict[str, Any] | None
) -> dict[str, Any]:
    if isinstance(verified_support, dict):
        return dict(verified_support)
    compatibility = skill_entry.get("compatibility") if isinstance(skill_entry, dict) else {}
    compatibility_verified = (
        compatibility.get("verified_support") if isinstance(compatibility, dict) else None
    )
    if isinstance(compatibility_verified, dict):
        return dict(compatibility_verified)
    current_verified = skill_entry.get("verified_support")
    return dict(current_verified) if isinstance(current_verified, dict) else {}


def build_inspect_payload(
    *,
    skill_entry: dict[str, Any],
    resolved_version: str,
    trust_state: str,
    verified_support: dict[str, Any] | None = None,
    dependency_view: dict[str, Any],
    provenance_view: dict[str, Any],
    distribution_view: dict[str, Any],
    trust_view: dict[str, Any],
    memory_hints: dict[str, Any],
) -> dict[str, Any]:
    runtime = dict(skill_entry.get("runtime") or {})
    verified_support_view = _resolved_verified_support(skill_entry, verified_support)
    install_targets = (
        runtime.get("install_targets") if isinstance(runtime.get("install_targets"), dict) else {}
    )
    return {
        "ok": True,
        "name": skill_entry.get("name"),
        "qualified_name": skill_entry.get("qualified_name"),
        "publisher": skill_entry.get("publisher"),
        "version": resolved_version,
        "latest_version": skill_entry.get("latest_version"),
        "trust_state": trust_state,
        "decision_metadata": canonical_decision_metadata(skill_entry),
        "compatibility": {
            "declared_support": _declared_support(skill_entry),
            "verified_support": verified_support_view,
            "state_summary": compatibility_summary(verified_support_view),
            "freshness_summary": compatibility_freshness_summary(verified_support_view),
        },
        "runtime": runtime,
        "runtime_readiness": (
            (runtime.get("readiness") or {}).get("status")
            if isinstance(runtime.get("readiness"), dict)
            else None
        ),
        "workspace_fit": {
            "scope": runtime.get("workspace_scope"),
            "targets": list(install_targets.get("workspace") or []),
        },
        "dependencies": dependency_view,
        "provenance": provenance_view,
        "distribution": distribution_view,
        "trust": trust_view,
        "memory_hints": memory_hints,
    }


__all__ = [
    "build_inspect_payload",
    "compatibility_freshness_summary",
    "compatibility_summary",
    "dependency_summary",
    "derive_trust_state",
]
