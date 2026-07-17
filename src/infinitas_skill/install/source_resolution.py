from __future__ import annotations

import json
import re
from collections.abc import Hashable, Iterable
from functools import cmp_to_key
from pathlib import Path
from typing import Any, TypeVar

from infinitas_skill.install.distribution_index import load_distribution_index
from infinitas_skill.install.registry_source_primitives import resolve_registry_root
from infinitas_skill.install.registry_sources import (
    load_registry_config,
    registry_identity,
)
from infinitas_skill.install.version_constraints import canonicalize_constraint, compare_versions
from infinitas_skill.policy.skill_identity import (
    derive_qualified_name,
    normalize_skill_identity,
    parse_requested_skill,
)

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
JsonDict = dict[str, Any]
T = TypeVar("T", bound=Hashable)


def _resolve_manifest_path(reg_root: Path, manifest_path: str | None) -> str:
    if not manifest_path:
        return str(reg_root)
    resolved = (reg_root / manifest_path).resolve()
    if not resolved.is_relative_to(reg_root):
        raise DependencyError(f"distribution manifest_path escapes registry root: {manifest_path}")
    return str(resolved)


class DependencyError(Exception):
    def __init__(self, message: str, details: JsonDict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


def unique(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    out: list[T] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def identity_key_for(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    identity = payload.get("qualified_name") or payload.get("name")
    return identity if isinstance(identity, str) else None


def display_identity(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    identity = payload.get("qualified_name") or payload.get("name")
    return identity if isinstance(identity, str) else None


def parse_dependency_identity(value: str, field: str) -> JsonDict:
    publisher, name = parse_requested_skill(value)
    if publisher is not None and not SKILL_NAME_RE.match(publisher):
        raise DependencyError(f"{field} entry has invalid publisher {publisher!r}")
    if not isinstance(name, str) or not SKILL_NAME_RE.match(name):
        raise DependencyError(f"{field} entry has invalid name {value!r}")
    qualified_name = derive_qualified_name(name, publisher) if publisher else None
    return {
        "name": name,
        "publisher": publisher,
        "qualified_name": qualified_name,
        "identity_key": qualified_name or name,
    }


def _normalize_entry(entry: object, field: str, owner_name: str | None = None) -> JsonDict:
    if isinstance(entry, str):
        raise DependencyError(f"{field} entries must use object format")
    elif isinstance(entry, dict):
        allowed_keys = {"name", "version", "registry", "allow_incubating"}
        unknown = sorted(set(entry) - allowed_keys)
        if unknown:
            raise DependencyError(
                f"{field} entry for {entry.get('name') or '<unknown>'} "
                f"has unsupported keys: {', '.join(unknown)}"
            )
        name = entry.get("name")
        if not isinstance(name, str):
            raise DependencyError(f"{field} entry has invalid name {name!r}")
        identity = parse_dependency_identity(name, field)
        version = entry.get("version", "*")
        if not isinstance(version, str):
            raise DependencyError(
                f"{field} entry for {identity['identity_key']} has non-string version constraint"
            )
        registry = entry.get("registry")
        if registry is not None and (not isinstance(registry, str) or not registry.strip()):
            raise DependencyError(
                f"{field} entry for {identity['identity_key']} "
                f"has invalid registry hint {registry!r}"
            )
        allow_incubating = entry.get("allow_incubating", False)
        if not isinstance(allow_incubating, bool):
            raise DependencyError(
                f"{field} entry for {identity['identity_key']} has non-boolean allow_incubating"
            )
        normalized = {
            **identity,
            "version": canonicalize_constraint(version),
            "registry": registry.strip()
            if isinstance(registry, str) and registry.strip()
            else None,
            "allow_incubating": allow_incubating,
            "format": "object",
            "raw": entry,
        }
    else:
        raise DependencyError(f"{field} entries must be objects")

    if owner_name and normalized["identity_key"] == owner_name:
        raise DependencyError(f"{field} cannot reference itself ({normalized['identity_key']})")
    return normalized


def normalize_meta_dependencies(
    meta: JsonDict, owner_name: str | None = None
) -> dict[str, list[JsonDict]]:
    owner_identity = normalize_skill_identity(meta)
    owner = owner_name or identity_key_for(owner_identity) or meta.get("name")
    normalized: dict[str, list[JsonDict]] = {}
    for field in ["depends_on", "conflicts_with"]:
        values = meta.get(field, []) or []
        if not isinstance(values, list):
            raise DependencyError(f"{field} must be an array")
        normalized[field] = [_normalize_entry(entry, field, owner) for entry in values]
    return normalized


def constraint_display(entry: JsonDict) -> str:
    registry = f" [{entry['registry']}]" if entry.get("registry") else ""
    version = entry.get("version") or "*"
    incubating = " +incubating" if entry.get("allow_incubating") else ""
    return f"{display_identity(entry) or entry['name']}{registry} {version}{incubating}".strip()


def load_meta(path: str | Path) -> JsonDict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _skill_candidate(
    *,
    reg_root: Path,
    registry_state: JsonDict,
    reg: JsonDict,
    index: int,
    stage: str,
    skill_dir: Path,
    meta: JsonDict,
    normalized: dict[str, list[JsonDict]],
    identity: JsonDict,
    distribution: JsonDict | None,
) -> JsonDict:
    dist = distribution or {}
    return {
        **registry_state,
        **identity,
        "name": meta.get("name"),
        "publisher": identity.get("publisher"),
        "qualified_name": identity.get("qualified_name"),
        "identity_mode": identity.get("identity_mode"),
        "identity_key": identity_key_for(identity) or meta.get("name"),
        "version": meta.get("version"),
        "status": meta.get("status"),
        "stage": dist.get("status") if distribution else stage,
        "path": _resolve_manifest_path(reg_root, dist.get("manifest_path"))
        if distribution
        else str(skill_dir),
        "skill_path": str(skill_dir),
        "dir_name": skill_dir.name,
        "relative_path": dist.get("manifest_path")
        if distribution
        else str(skill_dir.relative_to(reg_root)),
        "installable": bool(meta.get("distribution", {}).get("installable", True)),
        "snapshot_of": meta.get("snapshot_of"),
        "snapshot_created_at": dist.get("generated_at")
        if distribution
        else meta.get("snapshot_created_at"),
        "depends_on": normalized["depends_on"],
        "conflicts_with": normalized["conflicts_with"],
        "meta": meta,
        "source_type": "distribution-manifest" if distribution else "working-tree",
        "distribution_manifest": dist.get("manifest_path") if distribution else None,
        "distribution_bundle": dist.get("bundle_path") if distribution else None,
        "distribution_bundle_sha256": dist.get("bundle_sha256") if distribution else None,
        "distribution_attestation": dist.get("attestation_path") if distribution else None,
        "distribution_attestation_signature": dist.get("attestation_signature_path")
        if distribution
        else None,
        "source_snapshot_kind": dist.get("source_snapshot_kind") if distribution else None,
        "source_snapshot_tag": dist.get("source_snapshot_tag") if distribution else None,
        "source_snapshot_ref": dist.get("source_snapshot_ref") if distribution else None,
        "source_snapshot_commit": dist.get("source_snapshot_commit") if distribution else None,
        "registry_commit": dist.get("source_snapshot_commit")
        if distribution
        else registry_state.get("registry_commit"),
        "registry_tag": dist.get("source_snapshot_tag")
        if distribution
        else registry_state.get("registry_tag"),
        "registry_ref": dist.get("source_snapshot_ref")
        if distribution
        else registry_state.get("registry_ref"),
        "registry_priority": int(reg.get("priority", 0)),
        "registry_order": index,
        "registry_enabled": reg.get("enabled", True),
    }


def _distribution_candidate(
    reg_root: Path,
    registry_state: JsonDict,
    reg: JsonDict,
    index: int,
    distribution: JsonDict,
) -> JsonDict:
    return {
        **registry_state,
        "name": distribution.get("name"),
        "publisher": distribution.get("publisher"),
        "qualified_name": distribution.get("qualified_name"),
        "identity_mode": distribution.get("identity_mode"),
        "identity_key": distribution.get("qualified_name") or distribution.get("name"),
        "version": distribution.get("version"),
        "status": distribution.get("status"),
        "stage": distribution.get("status") or "archived",
        "path": _resolve_manifest_path(reg_root, distribution.get("manifest_path")),
        "skill_path": None,
        "dir_name": Path(distribution.get("manifest_path") or "").parent.name,
        "relative_path": distribution.get("manifest_path"),
        "installable": True,
        "snapshot_of": None,
        "snapshot_created_at": distribution.get("generated_at"),
        "depends_on": distribution.get("depends_on", []),
        "conflicts_with": distribution.get("conflicts_with", []),
        "meta": {"name": distribution.get("name"), "version": distribution.get("version")},
        "source_type": "distribution-manifest",
        "distribution_manifest": distribution.get("manifest_path"),
        "distribution_bundle": distribution.get("bundle_path"),
        "distribution_bundle_sha256": distribution.get("bundle_sha256"),
        "distribution_attestation": distribution.get("attestation_path"),
        "distribution_attestation_signature": distribution.get("attestation_signature_path"),
        "source_snapshot_kind": distribution.get("source_snapshot_kind"),
        "source_snapshot_tag": distribution.get("source_snapshot_tag"),
        "source_snapshot_ref": distribution.get("source_snapshot_ref"),
        "source_snapshot_commit": distribution.get("source_snapshot_commit"),
        "registry_commit": distribution.get("source_snapshot_commit")
        or registry_state.get("registry_commit"),
        "registry_tag": distribution.get("source_snapshot_tag")
        or registry_state.get("registry_tag"),
        "registry_ref": distribution.get("source_snapshot_ref")
        or registry_state.get("registry_ref"),
        "registry_priority": int(reg.get("priority", 0)),
        "registry_order": index,
        "registry_enabled": reg.get("enabled", True),
    }


def _candidate_indexes(
    candidates: Iterable[JsonDict],
) -> tuple[dict[str, list[JsonDict]], dict[str, list[JsonDict]]]:
    by_name: dict[str, list[JsonDict]] = {}
    by_identity: dict[str, list[JsonDict]] = {}
    for candidate in candidates:
        name = candidate.get("name")
        identity_key = candidate.get("identity_key") or name
        if isinstance(name, str):
            by_name.setdefault(name, []).append(candidate)
        if isinstance(identity_key, str):
            by_identity.setdefault(identity_key, []).append(candidate)
    for mapping in (by_name, by_identity):
        for key in list(mapping):
            mapping[key] = sorted(mapping[key], key=cmp_to_key(_candidate_catalog_compare))
    return by_name, by_identity


def scan_enabled_registry_skills(root: Path) -> JsonDict:
    cfg = load_registry_config(root)
    enabled = [reg for reg in cfg.get("registries", []) if reg.get("enabled", True)]
    sorted_registries = sorted(
        enabled,
        key=lambda reg: (-int(reg.get("priority", 0)), reg.get("name") or ""),
    )
    registry_identities: dict[str, JsonDict] = {}
    registry_roots: dict[str, Path | None] = {}
    missing_roots: dict[str, str | None] = {}
    candidates: list[JsonDict] = []
    for index, reg in enumerate(sorted_registries):
        reg_name = reg.get("name")
        if not isinstance(reg_name, str) or not reg_name:
            raise DependencyError("enabled registry is missing a name")
        reg_root = resolve_registry_root(root, reg)
        registry_roots[reg_name] = reg_root
        if reg_root is None or not reg_root.exists():
            missing_roots[reg_name] = str(reg_root) if reg_root else None
            continue
        registry_state = registry_identity(root, reg)
        registry_identities[reg_name] = registry_state
        distribution_index = load_distribution_index(reg_root)
        distribution_by_identity = {
            (entry.get("qualified_name") or entry.get("name"), entry.get("version")): entry
            for entry in distribution_index
        }
        matched_distribution: set[tuple[object, object]] = set()
        skills_root = reg_root / "skills"
        for stage in ["active", "incubating", "archived"]:
            stage_dir = skills_root / stage
            if not stage_dir.exists():
                continue
            for skill_dir in sorted(
                path
                for path in stage_dir.iterdir()
                if path.is_dir() and (path / "_meta.json").exists()
            ):
                meta = load_meta(skill_dir / "_meta.json")
                normalized = normalize_meta_dependencies(meta)
                skill_identity = normalize_skill_identity(meta)
                distribution = distribution_by_identity.get(
                    (skill_identity.get("qualified_name") or meta.get("name"), meta.get("version"))
                )
                candidates.append(
                    _skill_candidate(
                        reg_root=reg_root,
                        registry_state=registry_state,
                        reg=reg,
                        index=index,
                        stage=stage,
                        skill_dir=skill_dir,
                        meta=meta,
                        normalized=normalized,
                        identity=skill_identity,
                        distribution=distribution,
                    )
                )
                if distribution:
                    matched_distribution.add(
                        (
                            skill_identity.get("qualified_name") or meta.get("name"),
                            meta.get("version"),
                        )
                    )
        for distribution in distribution_index:
            key = (
                distribution.get("qualified_name") or distribution.get("name"),
                distribution.get("version"),
            )
            if key in matched_distribution:
                continue
            candidates.append(
                _distribution_candidate(reg_root, registry_state, reg, index, distribution)
            )
    by_name, by_identity = _candidate_indexes(candidates)
    return {
        "config": cfg,
        "registries": sorted_registries,
        "registry_roots": registry_roots,
        "registry_identities": registry_identities,
        "missing_roots": missing_roots,
        "candidates": candidates,
        "by_name": by_name,
        "by_identity": by_identity,
    }


def _candidate_catalog_compare(left: JsonDict, right: JsonDict) -> int:
    if left["registry_priority"] != right["registry_priority"]:
        return -1 if left["registry_priority"] > right["registry_priority"] else 1
    left_source = 0 if left.get("source_type") == "distribution-manifest" else 1
    right_source = 0 if right.get("source_type") == "distribution-manifest" else 1
    if left_source != right_source:
        return -1 if left_source < right_source else 1
    stage_order = {"active": 0, "incubating": 1, "archived": 2}
    left_stage_value = left.get("stage")
    right_stage_value = right.get("stage")
    left_stage = stage_order.get(left_stage_value, 9) if isinstance(left_stage_value, str) else 9
    right_stage = stage_order.get(right_stage_value, 9) if isinstance(right_stage_value, str) else 9
    if left_stage != right_stage:
        return -1 if left_stage < right_stage else 1
    version_cmp = compare_versions(right.get("version") or "0.0.0", left.get("version") or "0.0.0")
    if version_cmp:
        return version_cmp
    left_snapshot = left.get("snapshot_created_at") or ""
    right_snapshot = right.get("snapshot_created_at") or ""
    if left_snapshot != right_snapshot:
        return -1 if left_snapshot > right_snapshot else 1
    left_key = (left.get("registry_name") or "", left.get("dir_name") or "", left.get("path") or "")
    right_key = (
        right.get("registry_name") or "",
        right.get("dir_name") or "",
        right.get("path") or "",
    )
    if left_key == right_key:
        return 0
    return -1 if left_key < right_key else 1


def candidate_from_skill_dir(
    skill_dir: str | Path,
    source_registry: str | None = None,
    source_info: JsonDict | None = None,
) -> JsonDict:
    skill_path = Path(skill_dir).resolve()
    if not skill_path.is_dir():
        raise DependencyError(f"skill path is not a directory: {skill_path}")
    meta = load_meta(skill_path / "_meta.json")
    normalized = normalize_meta_dependencies(meta)
    identity = normalize_skill_identity(meta)
    info = source_info or {}
    return {
        **info,
        **identity,
        "name": meta.get("name"),
        "publisher": identity.get("publisher"),
        "qualified_name": identity.get("qualified_name"),
        "identity_mode": identity.get("identity_mode"),
        "identity_key": identity_key_for(identity) or meta.get("name"),
        "version": meta.get("version"),
        "status": meta.get("status"),
        "stage": info.get("stage") or skill_path.parent.name,
        "path": str(skill_path),
        "skill_path": str(skill_path),
        "dir_name": skill_path.name,
        "relative_path": info.get("relative_path"),
        "installable": bool(meta.get("distribution", {}).get("installable", True)),
        "snapshot_of": meta.get("snapshot_of"),
        "snapshot_created_at": meta.get("snapshot_created_at"),
        "depends_on": normalized["depends_on"],
        "conflicts_with": normalized["conflicts_with"],
        "meta": meta,
        "registry_name": source_registry
        or info.get("registry_name")
        or info.get("source_registry")
        or "self",
        "registry_priority": int(info.get("registry_priority", 0) or 0),
        "source_type": info.get("source_type") or "working-tree",
        "distribution_manifest": info.get("distribution_manifest"),
        "distribution_bundle": info.get("distribution_bundle"),
        "distribution_bundle_sha256": info.get("distribution_bundle_sha256"),
        "distribution_attestation": info.get("distribution_attestation"),
        "distribution_attestation_signature": info.get("distribution_attestation_signature"),
        "source_snapshot_kind": info.get("source_snapshot_kind"),
        "source_snapshot_tag": info.get("source_snapshot_tag"),
        "source_snapshot_ref": info.get("source_snapshot_ref"),
        "source_snapshot_commit": info.get("source_snapshot_commit"),
    }
