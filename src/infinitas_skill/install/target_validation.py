from __future__ import annotations

from functools import cmp_to_key
from pathlib import Path
from typing import Any

from infinitas_skill.install.install_manifest import InstallManifestError, load_install_manifest
from infinitas_skill.install.source_resolution import (
    DependencyError,
    constraint_display,
    display_identity,
    identity_key_for,
    load_meta,
    normalize_meta_dependencies,
    unique,
)
from infinitas_skill.install.version_constraints import (
    compare_versions,
    constraint_is_exact,
    version_satisfies,
)
from infinitas_skill.openclaw.workspace import resolve_openclaw_skill_dirs
from infinitas_skill.policy.skill_identity import normalize_skill_identity
from infinitas_skill.root import ROOT

JsonDict = dict[str, Any]


class CandidateComparator:
    def __init__(
        self,
        *,
        preferred: list[str],
        installed_item: JsonDict | None,
        exact_only: bool,
    ) -> None:
        self.preferred = preferred
        self.installed_item = installed_item
        self.stage_order = (
            {"archived": 0, "active": 1, "incubating": 2}
            if exact_only
            else {"active": 0, "incubating": 1, "archived": 2}
        )

    @staticmethod
    def _compare_values(left: Any, right: Any) -> int:
        if left == right:
            return 0
        return -1 if left < right else 1

    def _registry_rank(self, candidate: JsonDict) -> int:
        name = candidate.get("registry_name")
        if isinstance(name, str) and name in self.preferred:
            return self.preferred.index(name)
        return len(self.preferred) + candidate.get("registry_order", 0)

    def _stage_rank(self, candidate: JsonDict) -> int:
        stage = candidate.get("stage")
        return self.stage_order.get(stage, 9) if isinstance(stage, str) else 9

    @staticmethod
    def _stable_key(candidate: JsonDict) -> tuple[str, str, str]:
        return (
            candidate.get("registry_name") or "",
            candidate.get("dir_name") or "",
            candidate.get("path") or "",
        )

    def __call__(self, left: JsonDict, right: JsonDict) -> int:
        comparisons = [
            (
                0 if installed_identity_matches(left, self.installed_item) else 1,
                0 if installed_identity_matches(right, self.installed_item) else 1,
            ),
            (self._registry_rank(left), self._registry_rank(right)),
            (
                0 if left.get("source_type") == "distribution-manifest" else 1,
                0 if right.get("source_type") == "distribution-manifest" else 1,
            ),
            (self._stage_rank(left), self._stage_rank(right)),
        ]
        for left_value, right_value in comparisons:
            result = self._compare_values(left_value, right_value)
            if result:
                return result
        version_result = compare_versions(
            right.get("version") or "0.0.0", left.get("version") or "0.0.0"
        )
        if version_result:
            return version_result
        snapshot_result = self._compare_values(
            right.get("snapshot_created_at") or "",
            left.get("snapshot_created_at") or "",
        )
        return snapshot_result or self._compare_values(
            self._stable_key(left), self._stable_key(right)
        )


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
) -> JsonDict:
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


def load_installed_state(target_dir: str | Path) -> dict[str, JsonDict]:
    target = Path(target_dir)
    try:
        manifest = load_install_manifest(target, allow_missing=True)
    except InstallManifestError as exc:
        raise DependencyError(str(exc)) from exc
    installed: dict[str, JsonDict] = {}
    manifest_skills = manifest.get("skills") or {}
    if target.exists():
        for child in sorted(
            path for path in target.iterdir() if path.is_dir() and (path / "_meta.json").exists()
        ):
            meta = load_meta(child / "_meta.json")
            normalized = normalize_meta_dependencies(meta)
            identity = normalize_skill_identity(meta)
            identity_key = identity_key_for(identity) or meta.get("name") or child.name
            if not isinstance(identity_key, str):
                raise DependencyError(f"installed skill is missing identity: {child}")
            entry: dict[str, Any] = {}
            lookup_keys = [
                key for key in [identity_key, meta.get("name"), child.name] if isinstance(key, str)
            ]
            for key in unique(lookup_keys):
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
        if not isinstance(identity_key, str):
            raise DependencyError(f"manifest skill is missing identity: {name}")
        if identity_key in installed:
            continue
        installed[identity_key] = {
            "name": entry.get("name") or name,
            "publisher": entry.get("publisher"),
            "qualified_name": entry.get("qualified_name"),
            "identity_mode": entry.get("identity_mode") or "qualified",
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


def entry_matches_skill(entry: JsonDict, skill: JsonDict) -> bool:
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


def constraints_compatible(constraints: list[JsonDict]) -> tuple[bool, str | None]:
    registries = unique(
        registry
        for entry in constraints
        if isinstance((registry := entry.get("registry")), str) and registry
    )
    if len(registries) > 1:
        return False, f"conflicting registry hints: {', '.join(registries)}"
    return True, None


def installed_identity_matches(candidate: JsonDict, installed: JsonDict | None) -> bool:
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


def candidate_satisfies_all(candidate: JsonDict, constraints: list[JsonDict]) -> bool:
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


def preferred_registries(constraints: list[JsonDict], catalog: JsonDict) -> list[str]:
    explicit = unique(
        registry
        for entry in constraints
        if isinstance((registry := entry.get("registry")), str) and registry
    )
    if explicit:
        return explicit
    from_sources = unique(
        registry
        for entry in constraints
        if isinstance((registry := entry.get("source_registry")), str) and registry
    )
    configured = [
        name
        for reg in catalog.get("registries", [])
        if isinstance((name := reg.get("name")), str) and name
    ]
    return unique(from_sources + configured)


def matching_candidates(
    requirement: JsonDict,
    constraints: list[JsonDict],
    installed_item: JsonDict | None,
    catalog: JsonDict,
) -> list[JsonDict]:
    preferred = preferred_registries(constraints, catalog)
    candidates: list[JsonDict] = []
    identity_key = requirement.get("identity_key") or requirement.get("name")
    candidate_pool = catalog["by_identity"].get(
        identity_key, catalog["by_name"].get(requirement.get("name"), [])
    )
    for candidate in candidate_pool:
        if candidate_satisfies_all(candidate, constraints):
            candidates.append(candidate)

    comparator = CandidateComparator(
        preferred=preferred,
        installed_item=installed_item,
        exact_only=all(constraint_is_exact(entry.get("version") or "*") for entry in constraints),
    )
    return sorted(candidates, key=cmp_to_key(comparator))


def selected_conflict_reason(candidate: JsonDict, selected: dict[str, JsonDict]) -> str | None:
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


def validate_final_state(
    root_candidate: JsonDict,
    selected: dict[str, JsonDict],
    installed: dict[str, JsonDict],
    mode: str,
) -> None:
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
        selected_installed_item = installed.get(identity_key)
        if not selected_installed_item:
            continue
        if mode == "install" and identity_key == root_identity:
            continue
        locked_version = selected_installed_item.get("locked_version")
        if locked_version and candidate.get("version") != locked_version:
            raise DependencyError(
                f"unsafe upgrade plan for {display_identity(candidate) or identity_key}: "
                f"installed copy is locked to {locked_version}",
                {
                    "skill": display_identity(candidate) or identity_key,
                    "selected": candidate_view(candidate),
                    "installed": installed_view(selected_installed_item),
                    "reason": "locked-version-mismatch",
                },
            )
