"""Collect normalized registry catalog entries from repository state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.compatibility.evidence import (
    load_compatibility_evidence,
    load_platform_contracts,
    merge_declared_and_verified_support,
)
from infinitas_skill.compatibility.policy import load_compatibility_policy
from infinitas_skill.install.distribution_materialization import manifest_index_entry
from infinitas_skill.install.registry_source_primitives import resolve_registry_root
from infinitas_skill.install.registry_sources import registry_identity
from infinitas_skill.policy.review_evaluation import evaluate_review_state
from infinitas_skill.policy.reviews import review_decision_entries
from infinitas_skill.policy.skill_identity import normalize_skill_identity
from infinitas_skill.release.transparency_log import summarize_transparency_log_state


def _expected_tag(name: Any, version: Any) -> str | None:
    if not name or not version:
        return None
    return f"skill/{name}/v{version}"


def _review_entries(skill_dir: Path) -> list[dict[str, Any]]:
    _reviews, entries = review_decision_entries(skill_dir)
    return [
        {
            "reviewer": item.get("reviewer"),
            "decision": item.get("decision"),
            "at": item.get("at"),
            "note": item.get("note"),
            "source": item.get("source"),
            "source_kind": item.get("source_kind"),
            "source_ref": item.get("source_ref"),
            "url": item.get("url"),
        }
        for item in entries
        if item.get("reviewer") and item.get("decision")
    ]


def stable_catalog_identity(
    root: Path, registry: dict[str, Any] | None, identity: dict[str, Any]
) -> dict[str, Any]:
    if registry is None:
        return identity
    if (
        resolve_registry_root(root, registry) == root
        and identity.get("registry_update_mode") == "local-only"
    ):
        stable = dict(identity)
        stable["registry_commit"] = None
        stable["registry_tag"] = None
        stable["registry_branch"] = None
        return stable
    return identity


def catalog_source_identity(
    root: Path, config: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    registries = list(config.get("registries") or [])
    source = next(
        (registry for registry in registries if resolve_registry_root(root, registry) == root),
        None,
    )
    if source is None:
        source = next(
            (
                registry
                for registry in registries
                if registry.get("name") == config.get("default_registry")
            ),
            None,
        )
    identity = registry_identity(root, source) if source else {}
    return source, stable_catalog_identity(root, source, identity)


def collect_distribution_entries(root: Path) -> list[dict[str, Any]]:
    distribution_root = root / "catalog" / "distributions"
    if not distribution_root.exists():
        return []
    return [
        manifest_index_entry(manifest_path, root)
        for manifest_path in sorted(distribution_root.rglob("manifest.json"))
    ]


def _distribution_key(entry: dict[str, Any]) -> tuple[Any, Any]:
    return entry.get("qualified_name") or entry.get("name"), entry.get("version")


def _base_skill_entry(
    *,
    root: Path,
    skill_dir: Path,
    stage: str,
    meta: dict[str, Any],
    review: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    identity = normalize_skill_identity(meta)
    return {
        "name": meta.get("name", skill_dir.name),
        "publisher": identity.get("publisher"),
        "qualified_name": identity.get("qualified_name"),
        "identity_mode": identity.get("identity_mode"),
        "version": meta.get("version"),
        "status": meta.get("status", stage),
        "summary": meta.get("summary", ""),
        "author": identity.get("author"),
        "owner": meta.get("owner"),
        "owners": identity.get("owners", []),
        "maintainers": meta.get("maintainers", []),
        "tags": meta.get("tags", []),
        "review_state": review.get("effective_review_state"),
        "declared_review_state": review.get("declared_review_state"),
        "risk_level": meta.get("risk_level"),
        "derived_from": meta.get("derived_from"),
        "snapshot_of": meta.get("snapshot_of"),
        "depends_on": meta.get("depends_on", []),
        "conflicts_with": meta.get("conflicts_with", []),
        "agent_compatible": meta.get("agent_compatible", []),
        "installable": bool((meta.get("distribution") or {}).get("installable", True)),
        "approval_count": review.get("approval_count"),
        "rejection_count": review.get("rejection_count"),
        "blocking_rejection_count": review.get("blocking_rejection_count"),
        "required_approvals": review.get("required_approvals"),
        "quorum_met": review.get("quorum_met"),
        "review_gate_pass": review.get("review_gate_pass"),
        "required_reviewer_groups": review.get("required_groups"),
        "covered_reviewer_groups": review.get("covered_groups"),
        "missing_reviewer_groups": review.get("missing_groups"),
        "reviewers": _review_entries(skill_dir),
        "path": str(skill_dir.relative_to(root)),
        "source_registry": source.get("registry_name"),
        "source_registry_url": source.get("registry_url"),
        "source_registry_ref": source.get("registry_ref"),
        "source_registry_commit": source.get("registry_commit"),
        "source_registry_tag": source.get("registry_tag"),
        "source_registry_trust": source.get("registry_trust"),
        "source_update_mode": source.get("registry_update_mode"),
        "source_pin_mode": source.get("registry_pin_mode"),
        "source_pin_value": source.get("registry_pin_value"),
        "expected_tag": _expected_tag(meta.get("name"), meta.get("version")),
    }


def _attach_distribution(
    root: Path, item: dict[str, Any], distribution: dict[str, Any] | None
) -> None:
    if distribution is None:
        return
    transparency = None
    attestation_path = distribution.get("attestation_path")
    if isinstance(attestation_path, str) and (root / attestation_path).exists():
        transparency = summarize_transparency_log_state(root / attestation_path, root=root)
    item["verified_distribution"] = {
        "manifest_path": distribution.get("manifest_path"),
        "bundle_path": distribution.get("bundle_path"),
        "bundle_sha256": distribution.get("bundle_sha256"),
        "file_manifest_count": distribution.get("file_manifest_count"),
        "build_archive_format": distribution.get("build_archive_format"),
        "installed_integrity_capability": distribution.get("installed_integrity_capability"),
        "installed_integrity_reason": distribution.get("installed_integrity_reason"),
        "attestation_path": attestation_path,
        "attestation_signature_path": distribution.get("attestation_signature_path"),
        "source_snapshot_tag": distribution.get("source_snapshot_tag"),
        "source_snapshot_commit": distribution.get("source_snapshot_commit"),
        "generated_at": distribution.get("generated_at"),
        "transparency_log": transparency,
    }


def collect_skill_entries(
    root: Path,
    *,
    source_identity: dict[str, Any],
    distribution_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    compatibility_evidence = load_compatibility_evidence(root)
    compatibility_policy = load_compatibility_policy(root)
    platform_contracts = load_platform_contracts(root)
    distributions = {_distribution_key(item): item for item in distribution_entries}
    entries: list[dict[str, Any]] = []
    for stage in ("incubating", "active", "archived"):
        stage_dir = root / "skills" / stage
        if not stage_dir.exists():
            continue
        for skill_dir in sorted(path for path in stage_dir.iterdir() if path.is_dir()):
            meta_path = skill_dir / "_meta.json"
            if not meta_path.exists() or not (skill_dir / "SKILL.md").exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            review = evaluate_review_state(skill_dir, root=root)
            item = _base_skill_entry(
                root=root,
                skill_dir=skill_dir,
                stage=stage,
                meta=meta,
                review=review,
                source=source_identity,
            )
            _attach_distribution(root, item, distributions.get(_distribution_key(item)))
            entries.append(
                merge_declared_and_verified_support(
                    item,
                    compatibility_evidence,
                    platform_contracts=platform_contracts,
                    compatibility_policy=compatibility_policy,
                )
            )
    return entries


__all__ = [
    "catalog_source_identity",
    "collect_distribution_entries",
    "collect_skill_entries",
    "stable_catalog_identity",
]
