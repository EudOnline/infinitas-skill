"""Install dependency planning orchestration built from focused modules."""

from __future__ import annotations

from pathlib import Path

from infinitas_skill.install.output import error_to_payload, plan_to_text
from infinitas_skill.install.plan_builder import build_plan, candidate_view
from infinitas_skill.install.source_resolution import (
    DependencyError,
    candidate_from_skill_dir,
    constraint_display,
    display_identity,
    normalize_meta_dependencies,
    scan_enabled_registry_skills,
)
from infinitas_skill.install.target_validation import (
    candidate_satisfies_all,
    constraints_compatible,
    load_installed_state,
    matching_candidates,
    selected_conflict_reason,
    validate_final_state,
)
from infinitas_skill.legacy import ROOT


class DependencyPlanner:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.catalog = scan_enabled_registry_skills(self.root)

    def plan(self, root_candidate, target_dir: str | Path | None = None, mode: str = "install"):
        installed = load_installed_state(target_dir) if target_dir else {}
        root_key = root_candidate.get("identity_key") or root_candidate.get("name")
        selected = {root_key: root_candidate}
        pending = [
            self._prepare_requirement(root_candidate, entry)
            for entry in root_candidate.get("depends_on", [])
        ]
        result = self._resolve_recursive(selected, pending, installed)
        validate_final_state(root_candidate, result, installed, mode)
        return build_plan(root_candidate, result, installed, self.catalog, mode)

    def _prepare_requirement(self, source_candidate, entry):
        return {
            **entry,
            "source_name": source_candidate.get("name"),
            "source_qualified_name": source_candidate.get("qualified_name"),
            "source_version": source_candidate.get("version"),
            "source_registry": source_candidate.get("registry_name"),
        }

    def _resolve_recursive(self, selected, pending, installed):
        if not pending:
            return selected

        pending_sorted = sorted(
            pending,
            key=lambda item: (
                item.get("identity_key") or item.get("name") or "",
                item.get("registry") or "",
                item.get("version") or "*",
                item.get("source_name") or "",
                item.get("source_version") or "",
            ),
        )
        requirement = pending_sorted[0]
        identity_key = requirement.get("identity_key") or requirement.get("name")
        display_name = display_identity(requirement) or requirement.get("name")

        remaining = pending_sorted[1:]
        same_name = [requirement]
        rest = []
        for item in remaining:
            if (item.get("identity_key") or item.get("name")) == identity_key:
                same_name.append(item)
            else:
                rest.append(item)

        okay, problem = constraints_compatible(same_name)
        if not okay:
            raise DependencyError(
                f"conflicting requirements for {display_name}",
                {
                    "skill": display_name,
                    "constraints": same_name,
                    "reason": problem,
                },
            )

        if identity_key in selected:
            candidate = selected[identity_key]
            if not candidate_satisfies_all(candidate, same_name):
                raise DependencyError(
                    f"selected dependency no longer satisfies all constraints for {display_name}",
                    {
                        "skill": display_name,
                        "selected": candidate_view(candidate),
                        "constraints": same_name,
                    },
                )
            return self._resolve_recursive(selected, rest, installed)

        candidate_matches = matching_candidates(
            requirement,
            same_name,
            installed.get(identity_key),
            self.catalog,
        )
        if not candidate_matches:
            available = [
                candidate_view(item) for item in self.catalog["by_identity"].get(identity_key, [])
            ]
            raise DependencyError(
                f"no registry candidate satisfies dependency {display_name}",
                {
                    "skill": display_name,
                    "constraints": same_name,
                    "available": available,
                    "missing_registry_roots": self.catalog.get("missing_roots", {}),
                },
            )

        rejected = []
        for candidate in candidate_matches:
            conflict = selected_conflict_reason(candidate, selected)
            if conflict:
                rejected.append({"candidate": candidate_view(candidate), "reason": conflict})
                continue

            next_selected = dict(selected)
            next_selected[candidate.get("identity_key") or candidate.get("name")] = candidate
            next_pending = list(rest)
            for dep in candidate.get("depends_on", []):
                next_pending.append(self._prepare_requirement(candidate, dep))

            try:
                return self._resolve_recursive(next_selected, next_pending, installed)
            except DependencyError as exc:
                rejected.append({"candidate": candidate_view(candidate), "reason": exc.message})

        raise DependencyError(
            f"no compatible resolution path found for {display_name}",
            {
                "skill": display_name,
                "constraints": same_name,
                "rejected_candidates": rejected,
            },
        )


def plan_from_skill_dir(
    skill_dir,
    target_dir: str | Path | None = None,
    source_registry: str | None = None,
    source_info=None,
    mode: str = "install",
):
    planner = DependencyPlanner(ROOT)
    root_candidate = candidate_from_skill_dir(
        skill_dir,
        source_registry=source_registry,
        source_info=source_info,
    )
    return planner.plan(root_candidate, target_dir=target_dir, mode=mode)


__all__ = [
    "DependencyError",
    "DependencyPlanner",
    "constraint_display",
    "error_to_payload",
    "normalize_meta_dependencies",
    "plan_from_skill_dir",
    "plan_to_text",
]
