"""Build catalog, registry, inventory, and audit export views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.discovery.ai_index import build_ai_index
from infinitas_skill.discovery.index import build_discovery_index
from infinitas_skill.install.registry_source_primitives import resolve_registry_root
from infinitas_skill.install.registry_sources import (
    registry_identity,
    registry_is_resolution_candidate,
)
from infinitas_skill.registry.catalog_entries import stable_catalog_identity
from infinitas_skill.registry.snapshot import snapshot_catalog_summary


def _compatibility_view(entries: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    stage_counts: dict[str, int] = {"incubating": 0, "active": 0, "archived": 0}
    agents: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        status = str(entry.get("status"))
        stage_counts[status] = stage_counts.get(status, 0) + 1
        for agent in entry.get("agent_compatible") or []:
            agents.setdefault(str(agent), []).append(
                {
                    "name": entry.get("name"),
                    "publisher": entry.get("publisher"),
                    "qualified_name": entry.get("qualified_name"),
                    "version": entry.get("version"),
                    "status": entry.get("status"),
                    "path": entry.get("path"),
                }
            )
    return {
        "generated_at": generated_at,
        "stage_counts": stage_counts,
        "agents": {
            key: sorted(value, key=lambda item: (item["name"], item["version"] or ""))
            for key, value in sorted(agents.items())
        },
        "skills": [
            {
                "name": entry.get("name"),
                "publisher": entry.get("publisher"),
                "qualified_name": entry.get("qualified_name"),
                "version": entry.get("version"),
                "status": entry.get("status"),
                "path": entry.get("path"),
                "declared_support": entry.get("declared_support") or [],
                "verified_support": entry.get("verified_support") or {},
            }
            for entry in sorted(
                entries, key=lambda item: (item.get("name") or "", item.get("version") or "")
            )
        ],
    }


def _resolved_root(root: Path, registry: dict[str, Any]) -> str | None:
    registry_root = resolve_registry_root(root, registry)
    if registry_root == root and (registry.get("update_policy") or {}).get("mode") == "local-only":
        return "."
    local_path = registry.get("local_path")
    if isinstance(local_path, str) and local_path:
        path = Path(local_path)
        return str(path.resolve() if path.is_absolute() else (root / path).resolve())
    if registry.get("kind") == "git":
        return str((root / ".cache" / "registries" / str(registry.get("name"))).resolve())
    return None


def build_registry_exports(
    root: Path, config: dict[str, Any], generated_at: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exports: list[dict[str, Any]] = []
    for registry in config.get("registries") or []:
        item = dict(registry)
        item["resolved_root"] = _resolved_root(root, registry)
        identity = stable_catalog_identity(root, registry, registry_identity(root, registry))
        item.update(
            {
                "resolved_ref": identity.get("registry_ref"),
                "resolved_commit": identity.get("registry_commit"),
                "resolved_tag": identity.get("registry_tag"),
                "resolved_origin_url": identity.get("registry_origin_url"),
                "resolved_federation_mode": identity.get("registry_federation_mode"),
                "resolved_allowed_publishers": identity.get("registry_allowed_publishers"),
                "resolved_publisher_map": identity.get("registry_publisher_map"),
                "resolved_require_immutable_artifacts": identity.get(
                    "registry_require_immutable_artifacts"
                ),
                "resolver_candidate": registry_is_resolution_candidate(registry),
            }
        )
        item.update(snapshot_catalog_summary(root, str(registry.get("name"))))
        exports.append(item)
    return (
        {
            "generated_at": generated_at,
            "default_registry": config.get("default_registry"),
            "registries": exports,
        },
        exports,
    )


def _inventory_skill(
    entry: dict[str, Any], registry_by_name: dict[Any, dict[str, Any]]
) -> dict[str, Any]:
    source_registry = registry_by_name.get(entry.get("source_registry"))
    distribution = entry.get("verified_distribution") or {}
    return {
        "name": entry.get("name"),
        "publisher": entry.get("publisher"),
        "qualified_name": entry.get("qualified_name"),
        "identity_mode": entry.get("identity_mode"),
        "version": entry.get("version"),
        "status": entry.get("status"),
        "summary": entry.get("summary"),
        "path": entry.get("path"),
        "installable": bool(entry.get("installable", False)),
        "released": bool(distribution.get("attestation_path")),
        "source_registry": entry.get("source_registry"),
        "source_registry_url": entry.get("source_registry_url"),
        "source_registry_trust": entry.get("source_registry_trust"),
        "source_registry_ref": entry.get("source_registry_ref"),
        "source_registry_commit": entry.get("source_registry_commit"),
        "source_registry_tag": entry.get("source_registry_tag"),
        "source_update_mode": entry.get("source_update_mode"),
        "source_pin_mode": entry.get("source_pin_mode"),
        "source_pin_value": entry.get("source_pin_value"),
        "source_federation_mode": source_registry.get("resolved_federation_mode")
        if source_registry
        else None,
        "resolver_candidate": source_registry.get("resolver_candidate")
        if source_registry
        else None,
        "distribution_manifest_path": distribution.get("manifest_path"),
        "distribution_bundle_path": distribution.get("bundle_path"),
        "release_attestation_path": distribution.get("attestation_path"),
        "release_attestation_signature_path": distribution.get("attestation_signature_path"),
        "release_source_snapshot_tag": distribution.get("source_snapshot_tag"),
        "release_source_snapshot_commit": distribution.get("source_snapshot_commit"),
        "release_file_manifest_count": distribution.get("file_manifest_count"),
        "release_build_archive_format": distribution.get("build_archive_format"),
        "release_installed_integrity_capability": distribution.get(
            "installed_integrity_capability"
        ),
        "release_installed_integrity_reason": distribution.get("installed_integrity_reason"),
    }


def build_inventory_export(
    *,
    config: dict[str, Any],
    entries: list[dict[str, Any]],
    registries: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    registry_by_name = {
        item.get("name"): item for item in registries if isinstance(item, dict) and item.get("name")
    }
    skills = [_inventory_skill(entry, registry_by_name) for entry in entries]
    return {
        "$schema": "../schemas/inventory-export.schema.json",
        "schema_version": 1,
        "generated_at": generated_at,
        "default_registry": config.get("default_registry"),
        "counts": {
            "registries": len(registries),
            "skills": len(skills),
            "installable_skills": sum(1 for item in skills if item.get("installable")),
            "released_skills": sum(1 for item in skills if item.get("released")),
        },
        "registries": [
            {
                "name": item.get("name"),
                "kind": item.get("kind"),
                "priority": item.get("priority"),
                "enabled": item.get("enabled"),
                "trust": item.get("trust"),
                "resolver_candidate": item.get("resolver_candidate"),
                "federation_mode": item.get("resolved_federation_mode"),
                "allowed_publishers": item.get("resolved_allowed_publishers"),
                "publisher_map": item.get("resolved_publisher_map"),
                "require_immutable_artifacts": item.get("resolved_require_immutable_artifacts"),
                "resolved_root": item.get("resolved_root"),
                "resolved_ref": item.get("resolved_ref"),
                "resolved_commit": item.get("resolved_commit"),
                "resolved_tag": item.get("resolved_tag"),
                "resolved_origin_url": item.get("resolved_origin_url"),
            }
            for item in registries
        ],
        "skills": sorted(
            skills, key=lambda item: (item.get("qualified_name") or "", item.get("version") or "")
        ),
    }


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def build_audit_export(
    root: Path, distributions: list[dict[str, Any]], generated_at: str
) -> dict[str, Any]:
    releases: list[dict[str, Any]] = []
    for entry in sorted(
        distributions,
        key=lambda item: (
            item.get("qualified_name") or item.get("name") or "",
            item.get("version") or "",
        ),
    ):
        provenance_ref = entry.get("attestation_path")
        if not isinstance(provenance_ref, str):
            continue
        provenance = _load_json_if_exists(root / provenance_ref)
        if provenance is None:
            continue
        releases.append(
            {
                "name": entry.get("name"),
                "publisher": entry.get("publisher"),
                "qualified_name": entry.get("qualified_name"),
                "identity_mode": entry.get("identity_mode"),
                "version": entry.get("version"),
                "status": entry.get("status"),
                "provenance_path": provenance_ref,
                "signature_path": entry.get("attestation_signature_path"),
                "manifest_path": entry.get("manifest_path"),
                "bundle_path": entry.get("bundle_path"),
                "bundle_sha256": entry.get("bundle_sha256"),
                "bundle_size": entry.get("bundle_size"),
                "source_snapshot": provenance.get("source_snapshot") or {},
                "review": provenance.get("review") or {},
                "release": provenance.get("release") or {},
                "registry": provenance.get("registry") or {},
                "dependencies": provenance.get("dependencies") or {},
            }
        )
    return {
        "$schema": "../schemas/audit-export.schema.json",
        "schema_version": 1,
        "generated_at": generated_at,
        "counts": {"releases": len(releases)},
        "releases": releases,
    }


def build_catalog_views(
    *,
    root: Path,
    config: dict[str, Any],
    entries: list[dict[str, Any]],
    distributions: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, dict[str, Any]]:
    catalog = {"generated_at": generated_at, "count": len(entries), "skills": entries}
    active_skills = [
        entry for entry in entries if entry.get("status") == "active" and entry.get("installable")
    ]
    registries_view, registry_entries = build_registry_exports(root, config, generated_at)
    ai_index = build_ai_index(
        root=root,
        catalog_entries=entries,
        distribution_entries=distributions,
    )
    ai_index["generated_at"] = generated_at
    discovery = build_discovery_index(root=root, local_ai_index=ai_index, registry_config=config)
    discovery["generated_at"] = generated_at
    return {
        "catalog.json": catalog,
        "active.json": {
            "generated_at": generated_at,
            "count": len(active_skills),
            "skills": active_skills,
        },
        "compatibility.json": _compatibility_view(entries, generated_at),
        "registries.json": registries_view,
        "distributions.json": {
            "generated_at": generated_at,
            "count": len(distributions),
            "skills": distributions,
        },
        "ai-index.json": ai_index,
        "discovery-index.json": discovery,
        "inventory-export.json": build_inventory_export(
            config=config,
            entries=entries,
            registries=registry_entries,
            generated_at=generated_at,
        ),
        "audit-export.json": build_audit_export(root, distributions, generated_at),
    }


__all__ = ["build_catalog_views"]
