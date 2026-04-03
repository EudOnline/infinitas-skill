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


def build_inspect_payload(
    *,
    skill_entry: dict[str, Any],
    resolved_version: str,
    trust_state: str,
    verified_support: dict[str, Any],
    dependency_view: dict[str, Any],
    provenance_view: dict[str, Any],
    distribution_view: dict[str, Any],
    trust_view: dict[str, Any],
    memory_hints: dict[str, Any],
) -> dict[str, Any]:
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
            "declared_support": (
                (skill_entry.get("compatibility") or {}).get("declared_support") or []
            ),
            "verified_support": verified_support,
            "verified_summary": compatibility_summary(verified_support),
            "freshness_summary": compatibility_freshness_summary(verified_support),
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
