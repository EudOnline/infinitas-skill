from __future__ import annotations

from functools import cmp_to_key
from pathlib import Path

from infinitas_skill.install.install_manifest import InstallManifestError, load_install_manifest
from infinitas_skill.install.source_resolution import (
    DependencyError,
    compare_versions,
    constraint_display,
    constraint_is_exact,
    display_identity,
    identity_key_for,
    load_meta,
    normalize_meta_dependencies,
    unique,
    version_satisfies,
)
from infinitas_skill.openclaw.workspace import resolve_openclaw_skill_dirs
from infinitas_skill.policy.skill_identity import normalize_skill_identity
from infinitas_skill.root import ROOT


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def resolve_openclaw_install_target(
    *,
    workspace_root: Path,
    target_dir: str | Path | None = None,
    workspace_scope: str = "workspace",
) -> dict:
    workspace_root = Path(workspace_root).resolve()
    candidates = [
        Path(path).resolve() for path in resolve_openclaw_skill_dirs(workspace_root, root=ROOT)
    ]
    if not candidates:
        fallback = (workspace_root / "skills").resolve()
        candidates = [fallback]

    workspace_targets = [path for path in candidates if _is_relative_to(path, workspace_root)]
    shared_targets = [path for path in candidates if path not in workspace_targets]

    if target_dir is not None:
        selected = Path(target_dir).resolve()
        selected_scope = "workspace" if _is_relative_to(selected, workspace_root) else "shared"
        selected_from = "explicit-target"
    else:
        if workspace_scope == "user" and shared_targets:
            selected = shared_targets[0]
            selected_scope = "shared"
        elif workspace_targets:
            selected = workspace_targets[0]
            selected_scope = "workspace"
        elif shared_targets:
            selected = shared_targets[0]
            selected_scope = "shared"
        else:
            selected = candidates[0]
            selected_scope = "workspace"
        selected_from = "runtime-default"

    return {
        "scope": selected_scope,
        "path": str(selected),
        "selected_from": selected_from,
        "workspace_targets": [str(path) for path in workspace_targets],
        "shared_targets": [str(path) for path in shared_targets],
        "candidates": [str(path) for path in candidates],
    }


def load_installed_state(target_dir):
    target = Path(target_dir)
    try:
        manifest = load_install_manifest(target, allow_missing=True)
    except InstallManifestError as exc:
        raise DependencyError(str(exc)) from exc
    installed = {}
    manifest_skills = manifest.get("skills") or {}
    if target.exists():
        for child in sorted(
            path for path in target.iterdir() if path.is_dir() and (path / "_meta.json").exists()
        ):
            meta = load_meta(child / "_meta.json")
            normalized = normalize_meta_dependencies(meta)
            identity = normalize_skill_identity(meta)
            identity_key = identity_key_for(identity) or meta.get("name") or child.name
            entry = {}
            for key in unique([identity_key, meta.get("name"), child.name]):
                if key and key in manifest_skills:
                    entry = manifest_skills.get(key) or {}
                    break
            installed[identity_key] = {
                **identity,
                "name": meta.get("name"),
                "publisher": identity.get("publisher"),
                "qualified_name": identity.get("qualified_name"),
                "identity_mode": identity.get("identity_mode"),
                "identity_key": identity_key,
                "version": meta.get("version") or entry.get("version"),
                "locked_version": entry.get("locked_version") or meta.get("version"),
                "source_registry": entry.get("source_registry"),
                "path": str(child),
                "meta": meta,
                "depends_on": normalized["depends_on"],
                "conflicts_with": normalized["conflicts_with"],
            }
    for name, entry in manifest_skills.items():
        identity_key = entry.get("qualified_name") or entry.get("name") or name
        if identity_key in installed:
            continue
        installed[identity_key] = {
            "name": entry.get("name") or name,
            "publisher": entry.get("publisher"),
            "qualified_name": entry.get("qualified_name"),
            "identity_mode": entry.get("identity_mode")
            or ("qualified" if entry.get("qualified_name") else "legacy"),
            "identity_key": identity_key,
            "version": entry.get("version") or entry.get("locked_version"),
            "locked_version": entry.get("locked_version"),
            "source_registry": entry.get("source_registry"),
            "path": str((target / (entry.get("name") or name)).resolve()),
            "meta": None,
            "depends_on": [],
            "conflicts_with": [],
        }
    return installed


def entry_matches_skill(entry, skill):
    if entry.get("qualified_name"):
        if entry.get("qualified_name") != skill.get("qualified_name"):
            return False
    else:
        if entry.get("name") != skill.get("name"):
            return False
        if entry.get("publisher") and entry.get("publisher") != skill.get("publisher"):
            return False
    if entry.get("registry") and entry.get("registry") != skill.get("registry_name"):
        return False
    version = skill.get("version")
    if not version:
        return False
    return version_satisfies(version, entry.get("version") or "*")


def constraints_compatible(constraints):
    registries = unique([entry.get("registry") for entry in constraints if entry.get("registry")])
    if len(registries) > 1:
        return False, f"conflicting registry hints: {', '.join(registries)}"
    return True, None


def installed_identity_matches(candidate, installed):
    if not installed:
        return False
    candidate_identity = (
        candidate.get("identity_key") or candidate.get("qualified_name") or candidate.get("name")
    )
    installed_identity = (
        installed.get("identity_key") or installed.get("qualified_name") or installed.get("name")
    )
    if candidate_identity and installed_identity and candidate_identity != installed_identity:
        return False
    installed_version = installed.get("version") or installed.get("locked_version")
    if installed_version and candidate.get("version") != installed_version:
        return False
    installed_registry = installed.get("source_registry")
    if installed_registry and candidate.get("registry_name") != installed_registry:
        return False
    return True


def candidate_satisfies_all(candidate, constraints):
    for entry in constraints:
        if entry.get("registry") and entry.get("registry") != candidate.get("registry_name"):
            return False
        if candidate.get("stage") == "incubating" and not entry.get("allow_incubating"):
            return False
        if candidate.get("stage") == "archived" and not constraint_is_exact(
            entry.get("version") or "*"
        ):
            return False
        if not version_satisfies(candidate.get("version") or "0.0.0", entry.get("version") or "*"):
            return False
    return bool(candidate.get("installable", True))


def preferred_registries(constraints, catalog):
    explicit = unique([entry.get("registry") for entry in constraints if entry.get("registry")])
    if explicit:
        return explicit
    from_sources = unique(
        [entry.get("source_registry") for entry in constraints if entry.get("source_registry")]
    )
    configured = [reg.get("name") for reg in catalog.get("registries", [])]
    return unique(from_sources + configured)


def matching_candidates(requirement, constraints, installed_item, catalog):
    preferred = preferred_registries(constraints, catalog)
    candidates = []
    identity_key = requirement.get("identity_key") or requirement.get("name")
    candidate_pool = catalog["by_identity"].get(
        identity_key, catalog["by_name"].get(requirement.get("name"), [])
    )
    for candidate in candidate_pool:
        if candidate_satisfies_all(candidate, constraints):
            candidates.append(candidate)

    exact_only = all(constraint_is_exact(entry.get("version") or "*") for entry in constraints)

    def compare(left, right):
        left_installed = 0 if installed_identity_matches(left, installed_item) else 1
        right_installed = 0 if installed_identity_matches(right, installed_item) else 1
        if left_installed != right_installed:
            return -1 if left_installed < right_installed else 1
        left_registry = (
            preferred.index(left.get("registry_name"))
            if left.get("registry_name") in preferred
            else len(preferred) + left.get("registry_order", 0)
        )
        right_registry = (
            preferred.index(right.get("registry_name"))
            if right.get("registry_name") in preferred
            else len(preferred) + right.get("registry_order", 0)
        )
        if left_registry != right_registry:
            return -1 if left_registry < right_registry else 1
        left_source = 0 if left.get("source_type") == "distribution-manifest" else 1
        right_source = 0 if right.get("source_type") == "distribution-manifest" else 1
        if left_source != right_source:
            return -1 if left_source < right_source else 1
        stage_order = (
            {"archived": 0, "active": 1, "incubating": 2}
            if exact_only
            else {"active": 0, "incubating": 1, "archived": 2}
        )
        left_stage = stage_order.get(left.get("stage"), 9)
        right_stage = stage_order.get(right.get("stage"), 9)
        if left_stage != right_stage:
            return -1 if left_stage < right_stage else 1
        version_cmp = compare_versions(
            right.get("version") or "0.0.0", left.get("version") or "0.0.0"
        )
        if version_cmp:
            return version_cmp
        left_snapshot = left.get("snapshot_created_at") or ""
        right_snapshot = right.get("snapshot_created_at") or ""
        if left_snapshot != right_snapshot:
            return -1 if left_snapshot > right_snapshot else 1
        left_key = (
            left.get("registry_name") or "",
            left.get("dir_name") or "",
            left.get("path") or "",
        )
        right_key = (
            right.get("registry_name") or "",
            right.get("dir_name") or "",
            right.get("path") or "",
        )
        if left_key == right_key:
            return 0
        return -1 if left_key < right_key else 1

    return sorted(candidates, key=cmp_to_key(compare))


def selected_conflict_reason(candidate, selected):
    candidate_identity = candidate.get("identity_key") or candidate.get("name")
    for other_identity, other in selected.items():
        if other_identity == candidate_identity:
            continue
        if other.get("name") == candidate.get("name"):
            return (
                f"cannot select both {display_identity(other)} and {display_identity(candidate)} "
                "because installed skill state is still keyed by bare skill name"
            )
        for conflict in candidate.get("conflicts_with", []):
            if entry_matches_skill(conflict, other):
                return (
                    f"{candidate.get('name')} conflicts with selected {other.get('name')} "
                    f"({constraint_display(conflict)})"
                )
        for conflict in other.get("conflicts_with", []):
            if entry_matches_skill(conflict, candidate):
                return (
                    f"selected {other.get('name')} conflicts with {candidate.get('name')} "
                    f"({constraint_display(conflict)})"
                )
    return None


def validate_final_state(root_candidate, selected, installed, mode):
    from infinitas_skill.install.plan_builder import candidate_view, installed_view

    selected_names = set(selected)
    for candidate in selected.values():
        for installed_item in installed.values():
            if (installed_item.get("identity_key") or installed_item.get("name")) in selected_names:
                continue
            for conflict in candidate.get("conflicts_with", []):
                if entry_matches_skill(conflict, installed_item):
                    message = (
                        f"{candidate.get('name')} conflicts with already installed "
                        f"{installed_item.get('name')}"
                    )
                    raise DependencyError(
                        message,
                        {
                            "skill": candidate.get("name"),
                            "selected": candidate_view(candidate),
                            "installed": installed_view(installed_item),
                            "conflict": conflict,
                        },
                    )
            for conflict in installed_item.get("conflicts_with", []):
                if entry_matches_skill(conflict, candidate):
                    message = (
                        f"already installed {installed_item.get('name')} "
                        f"conflicts with {candidate.get('name')}"
                    )
                    raise DependencyError(
                        message,
                        {
                            "skill": candidate.get("name"),
                            "selected": candidate_view(candidate),
                            "installed": installed_view(installed_item),
                            "conflict": conflict,
                        },
                    )
    root_identity = root_candidate.get("identity_key") or root_candidate.get("name")
    for identity_key, candidate in selected.items():
        installed_item = installed.get(identity_key)
        if not installed_item:
            continue
        if mode == "install" and identity_key == root_identity:
            continue
        locked_version = installed_item.get("locked_version")
        if locked_version and candidate.get("version") != locked_version:
            raise DependencyError(
                f"unsafe upgrade plan for {display_identity(candidate) or identity_key}: "
                f"installed copy is locked to {locked_version}",
                {
                    "skill": display_identity(candidate) or identity_key,
                    "selected": candidate_view(candidate),
                    "installed": installed_view(installed_item),
                    "reason": "locked-version-mismatch",
                },
            )
