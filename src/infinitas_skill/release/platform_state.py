from __future__ import annotations

import importlib

from infinitas_skill.compatibility.policy import load_compatibility_policy
from infinitas_skill.legacy import ROOT, ensure_legacy_scripts_on_path

ensure_legacy_scripts_on_path(ROOT)

compatibility_evidence_lib = importlib.import_module("compatibility_evidence_lib")

load_compatibility_evidence = compatibility_evidence_lib.load_compatibility_evidence
load_platform_contracts = compatibility_evidence_lib.load_platform_contracts
merge_declared_and_verified_support = compatibility_evidence_lib.merge_declared_and_verified_support

BLOCKING_PLATFORM_STATES = {"unknown", "blocked", "broken", "unsupported"}
BLOCKING_FRESHNESS_STATES = {"stale", "unknown"}


def collect_platform_compatibility_state(root, meta, identity):
    compatibility_policy = load_compatibility_policy(root)
    platform_contracts = load_platform_contracts(root)
    compatibility_evidence = load_compatibility_evidence(root)
    merged = merge_declared_and_verified_support(
        {
            "name": meta.get("name"),
            "qualified_name": identity.get("qualified_name"),
            "version": meta.get("version"),
            "declared_support": meta.get("agent_compatible") or [],
            "agent_compatible": meta.get("agent_compatible") or [],
        },
        compatibility_evidence,
        platform_contracts=platform_contracts,
        compatibility_policy=compatibility_policy,
    )
    declared_support = merged.get("declared_support") or []
    verified_support = merged.get("verified_support") or {}
    blocking_platforms = []
    for platform in declared_support:
        item = dict(verified_support.get(platform) or {})
        state = item.get("state") or "unknown"
        freshness_state = item.get("freshness_state") or "unknown"
        if state in BLOCKING_PLATFORM_STATES or freshness_state in BLOCKING_FRESHNESS_STATES:
            item["platform"] = platform
            blocking_platforms.append(item)

    return {
        "declared_support": declared_support,
        "verified_support": verified_support,
        "blocking_platforms": blocking_platforms,
        "policy": (compatibility_policy.get("verified_support") or {}),
        "evaluation_error": None,
    }


def format_blocking_platform_support(item):
    parts = []
    state = item.get("state") or "unknown"
    freshness_state = item.get("freshness_state") or "unknown"
    parts.append(f"state={state}")
    parts.append(f"freshness={freshness_state}")
    freshness_reason = item.get("freshness_reason")
    if freshness_reason:
        parts.append(f"reason={freshness_reason}")
    checked_at = item.get("checked_at")
    if checked_at:
        parts.append(f"checked_at={checked_at}")
    contract_last_verified = item.get("contract_last_verified")
    if contract_last_verified:
        parts.append(f"contract_last_verified={contract_last_verified}")
    return f"{item.get('platform') or 'unknown'} ({', '.join(parts)})"


__all__ = [
    "collect_platform_compatibility_state",
    "format_blocking_platform_support",
]
