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
    resolve_openclaw_install_target,
    selected_conflict_reason,
    validate_final_state,
)
from infinitas_skill.openclaw.plugins import normalize_plugin_capabilities
from infinitas_skill.openclaw.runtime_model import build_openclaw_runtime_model
from infinitas_skill.root import ROOT


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if token and token not in out:
            out.append(token)
    return out


def resolve_memory_mode_selection(
    *,
    supported_modes: object,
    default_mode: object,
    requested_mode: str | None = None,
) -> dict[str, object]:
    supported = _string_list(supported_modes)
    normalized_default = (
        str(default_mode).strip() if isinstance(default_mode, str) and default_mode.strip() else None
    )
    if normalized_default not in supported:
        normalized_default = supported[0] if supported else None
    normalized_requested = (
        str(requested_mode).strip()
        if isinstance(requested_mode, str) and requested_mode.strip()
        else None
    )
    if normalized_requested is not None and normalized_requested not in supported:
        raise DependencyError(
            f"unsupported memory mode: {normalized_requested}",
            {
                "supported_memory_modes": supported,
                "default_memory_mode": normalized_default,
                "requested_memory_mode": normalized_requested,
            },
        )
    selected = normalized_requested or normalized_default
    return {
        "supported_memory_modes": supported,
        "default_memory_mode": normalized_default,
        "selected_memory_mode": selected,
    }


def _bool_required(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("required"), bool):
            return value["required"]
        if isinstance(value.get("enabled"), bool):
            return value["enabled"]
    return False


def _openclaw_requires(meta: dict) -> dict[str, list[str]]:
    requires = meta.get("requires") if isinstance(meta.get("requires"), dict) else {}
    metadata_openclaw = (meta.get("metadata") or {}).get("openclaw")
    openclaw_requires = (
        metadata_openclaw.get("requires")
        if isinstance(metadata_openclaw, dict) and isinstance(metadata_openclaw.get("requires"), dict)
        else {}
    )
    bins = _string_list(requires.get("bins")) + _string_list(openclaw_requires.get("bins"))
    env = _string_list(requires.get("env")) + _string_list(openclaw_requires.get("env"))
    return {
        "tools": _string_list(requires.get("tools")),
        "bins": _string_list(bins),
        "env": _string_list(env),
        "config": _string_list(openclaw_requires.get("config")),
    }


def _runtime_readiness(
    *,
    supports_plugins: bool,
    supports_background_tasks: bool,
    supports_subagents: bool,
    plugin_required: dict[str, list[str]],
    background_required: bool,
    subagents_required: bool,
) -> dict:
    ready = (
        (supports_plugins or not plugin_required)
        and (supports_background_tasks or not background_required)
        and (supports_subagents or not subagents_required)
    )
    if not supports_plugins and plugin_required:
        status = "missing-plugin-support"
    elif not supports_background_tasks and background_required:
        status = "missing-background-task-support"
    elif not supports_subagents and subagents_required:
        status = "missing-subagent-support"
    else:
        status = "ready"
    return {"ready": ready, "status": status}


def _build_openclaw_runtime_install_view(
    *,
    root_candidate: dict,
    install_target: dict,
) -> dict:
    meta = root_candidate.get("meta") if isinstance(root_candidate.get("meta"), dict) else {}
    runtime_meta = (
        meta.get("openclaw_runtime") if isinstance(meta.get("openclaw_runtime"), dict) else {}
    )
    plugin_required = normalize_plugin_capabilities(runtime_meta.get("plugin_capabilities"))
    background_required = _bool_required(runtime_meta.get("background_tasks"))
    subagents_required = _bool_required(runtime_meta.get("subagents"))

    runtime_model = build_openclaw_runtime_model(ROOT)
    capabilities = dict(runtime_model.get("capabilities") or {})
    readiness = _runtime_readiness(
        supports_plugins=capabilities.get("supports_plugins") is True,
        supports_background_tasks=capabilities.get("supports_background_tasks") is True,
        supports_subagents=capabilities.get("supports_subagents") is True,
        plugin_required=plugin_required,
        background_required=background_required,
        subagents_required=subagents_required,
    )

    return {
        "platform": "openclaw",
        "workspace_scope": install_target.get("scope") or "workspace",
        "install_target": dict(install_target),
        "workspace_fit": {
            "status": "workspace-target"
            if install_target.get("scope") == "workspace"
            else "shared-target",
            "workspace_targets": list(install_target.get("workspace_targets") or []),
            "shared_targets": list(install_target.get("shared_targets") or []),
        },
        "requires": _openclaw_requires(meta),
        "plugin_needs": {"required": plugin_required},
        "background_tasks": {"required": background_required},
        "subagents": {"required": subagents_required},
        "readiness": readiness,
    }


class DependencyPlanner:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.catalog = scan_enabled_registry_skills(self.root)

    def plan(
        self,
        root_candidate,
        target_dir: str | Path | None = None,
        mode: str = "install",
        install_target: dict | None = None,
    ):
        install_target_payload = dict(install_target or {})
        installed_dir = install_target_payload.get("path") or target_dir
        installed = load_installed_state(installed_dir) if installed_dir else {}
        root_key = root_candidate.get("identity_key") or root_candidate.get("name")
        selected = {root_key: root_candidate}
        pending = [
            self._prepare_requirement(root_candidate, entry)
            for entry in root_candidate.get("depends_on", [])
        ]
        result = self._resolve_recursive(selected, pending, installed)
        validate_final_state(root_candidate, result, installed, mode)
        plan = build_plan(root_candidate, result, installed, self.catalog, mode)
        runtime_view = _build_openclaw_runtime_install_view(
            root_candidate=root_candidate,
            install_target=install_target_payload,
        )
        plan["runtime"] = runtime_view
        plan["install_target"] = dict(runtime_view.get("install_target") or {})
        plan["root"]["runtime"] = dict(runtime_view)
        for step in plan.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step["runtime"] = {
                "platform": runtime_view.get("platform"),
                "install_target": dict(runtime_view.get("install_target") or {}),
                "workspace_fit": dict(runtime_view.get("workspace_fit") or {}),
                "readiness": dict(runtime_view.get("readiness") or {}),
            }
        return plan

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
    meta = root_candidate.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    runtime_meta = meta.get("openclaw_runtime")
    runtime_meta = runtime_meta if isinstance(runtime_meta, dict) else {}
    workspace_scope = runtime_meta.get("workspace_scope")
    if not isinstance(workspace_scope, str) or workspace_scope not in {"workspace", "user"}:
        workspace_scope = "workspace"
    workspace_root = (
        Path(target_dir).resolve()
        if target_dir is not None
        else Path(skill_dir).resolve().parent
    )
    install_target = resolve_openclaw_install_target(
        workspace_root=workspace_root,
        target_dir=target_dir,
        workspace_scope=workspace_scope,
    )
    return planner.plan(
        root_candidate,
        target_dir=target_dir,
        mode=mode,
        install_target=install_target,
    )


def plan_from_registry_entry(entry: dict, *, memory_mode: str | None = None) -> dict:
    kind = str(entry.get("kind") or entry.get("object_kind") or "skill")
    memory_selection = resolve_memory_mode_selection(
        supported_modes=entry.get("supported_memory_modes"),
        default_mode=entry.get("default_memory_mode"),
        requested_mode=memory_mode,
    )
    supported_memory_modes = list(memory_selection["supported_memory_modes"])
    default_memory_mode = memory_selection["default_memory_mode"]
    selected_memory_mode = None
    if kind == "agent_preset":
        selected_memory_mode = memory_selection["selected_memory_mode"]

    root = {
        "kind": kind,
        "name": entry.get("name"),
        "qualified_name": entry.get("qualified_name") or entry.get("name"),
        "version": entry.get("default_install_version") or entry.get("latest_version"),
        "publisher": entry.get("publisher"),
        "selected_memory_mode": selected_memory_mode,
        "default_memory_mode": default_memory_mode,
        "supported_memory_modes": supported_memory_modes,
    }
    step = {
        "order": 1,
        "action": "install",
        "kind": kind,
        "name": root["name"],
        "qualified_name": root["qualified_name"],
        "version": root["version"],
        "manifest_path": ((entry.get("versions") or {}).get(root["version"]) or {}).get("manifest_path"),
        "bundle_path": ((entry.get("versions") or {}).get(root["version"]) or {}).get("bundle_path"),
        "selected_memory_mode": selected_memory_mode,
    }
    return {
        "mode": "install",
        "root": root,
        "steps": [step],
        "runtime": dict(entry.get("runtime") or {}),
    }


__all__ = [
    "DependencyError",
    "DependencyPlanner",
    "constraint_display",
    "error_to_payload",
    "normalize_meta_dependencies",
    "plan_from_skill_dir",
    "resolve_memory_mode_selection",
    "plan_to_text",
]
