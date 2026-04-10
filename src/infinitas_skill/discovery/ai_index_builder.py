from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.openclaw.contracts import OpenClawContractError
from infinitas_skill.openclaw.plugins import normalize_plugin_capabilities
from infinitas_skill.openclaw.runtime_model import build_openclaw_runtime_model
from infinitas_skill.openclaw.skill_contract import (
    OpenClawSkillContractError,
    load_openclaw_skill_contract,
)
from infinitas_skill.root import ROOT

from .decision_metadata import canonical_decision_metadata

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$")

INSTALL_POLICY = {
    "mode": "immutable-only",
    "direct_source_install_allowed": False,
    "require_attestation": True,
    "require_sha256": True,
}


def _default_openclaw_runtime_targets() -> list[str]:
    try:
        runtime_model = build_openclaw_runtime_model(ROOT)
        return list(runtime_model.get("skill_dir_candidates") or [])
    except OpenClawContractError:
        return ["skills", ".agents/skills", "~/.agents/skills", "~/.openclaw/skills"]


OPENCLAW_INTEROP = {
    "runtime_targets": _default_openclaw_runtime_targets(),
    "import_supported": True,
    "export_supported": True,
    "public_publish": {
        "clawhub": {
            "supported": True,
            "default": False,
        }
    },
}


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _semver_key(value):
    if not isinstance(value, str):
        return (-1, -1, -1, -1, "")
    match = SEMVER_RE.match(value.strip())
    if not match:
        return (-1, -1, -1, -1, value)
    major, minor, patch, suffix = match.groups()
    stability = 1 if suffix is None else 0
    return (int(major), int(minor), int(patch), stability, suffix or "")


def _sort_versions(values):
    unique = []
    for value in values:
        if isinstance(value, str) and value not in unique:
            unique.append(value)
    return sorted(unique, key=_semver_key, reverse=True)


def _relative_repo_path(value):
    if not isinstance(value, str) or not value.strip():
        return False
    return not Path(value).is_absolute()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def _bool_required(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("required"), bool):
            return value["required"]
        if isinstance(value.get("enabled"), bool):
            return value["enabled"]
    return False


def _load_runtime_model(root: Path) -> dict:
    try:
        return build_openclaw_runtime_model(root)
    except OpenClawContractError:
        return build_openclaw_runtime_model(ROOT)


def _catalog_entry_by_key(entries):
    lookup = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("qualified_name") or entry.get("name")
        if not key:
            continue
        current = lookup.get(key)
        if current is None or _semver_key(entry.get("version")) > _semver_key(
            current.get("version")
        ):
            lookup[key] = entry
    return lookup


def _meta_for_entry(root: Path, entry):
    rel_path = entry.get("path")
    if not isinstance(rel_path, str) or not rel_path:
        return {}
    meta_path = root / rel_path / "_meta.json"
    if not meta_path.exists():
        return {}
    try:
        return _load_json(meta_path)
    except Exception:
        return {}


def _publisher_for_entry(current, meta):
    for candidate in [
        current.get("publisher") if isinstance(current, dict) else None,
        current.get("owner") if isinstance(current, dict) else None,
        meta.get("publisher") if isinstance(meta, dict) else None,
        meta.get("owner") if isinstance(meta, dict) else None,
        meta.get("author") if isinstance(meta, dict) else None,
    ]:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _trust_state_from_version_entry(version_entry):
    if not isinstance(version_entry, dict):
        return "unknown"
    if version_entry.get("attestation_signature_path"):
        return "verified"
    if version_entry.get("attestation_path"):
        return "attested"
    if version_entry.get("installable"):
        return "installable"
    return "unknown"


def _last_verified_at(verified_support, meta):
    newest = None
    if isinstance(verified_support, dict):
        for payload in verified_support.values():
            if not isinstance(payload, dict):
                continue
            checked_at = payload.get("checked_at")
            if isinstance(checked_at, str) and checked_at.strip():
                if newest is None or checked_at > newest:
                    newest = checked_at
    if newest:
        return newest
    fallback = meta.get("last_verified_at") if isinstance(meta, dict) else None
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def _skill_path_for_entry(root: Path, entry: dict) -> Path | None:
    rel_path = entry.get("path")
    if not isinstance(rel_path, str) or not rel_path.strip():
        return None
    return (root / rel_path).resolve()


def _openclaw_runtime_contract(root: Path, entry: dict) -> dict:
    skill_path = _skill_path_for_entry(root, entry)
    if skill_path is None or not skill_path.exists():
        return {}
    try:
        return load_openclaw_skill_contract(skill_path)
    except OpenClawSkillContractError:
        return {}


def _runtime_targets(runtime_model: dict) -> list[str]:
    targets = list(runtime_model.get("skill_dir_candidates") or [])
    return targets or ["skills", ".agents/skills", "~/.agents/skills", "~/.openclaw/skills"]


def _install_targets_from_runtime(runtime_targets: list[str]) -> dict[str, list[str]]:
    workspace: list[str] = []
    shared: list[str] = []
    for target in runtime_targets:
        if target.startswith("~/") or Path(target).is_absolute():
            if target not in shared:
                shared.append(target)
        else:
            if target not in workspace:
                workspace.append(target)
    return {"workspace": workspace, "shared": shared}


def _requires_detail(meta: dict, requires: dict, runtime_contract: dict) -> dict[str, list[str]]:
    metadata_openclaw = (meta.get("metadata") or {}).get("openclaw")
    openclaw_requires = (
        metadata_openclaw.get("requires")
        if isinstance(metadata_openclaw, dict)
        and isinstance(metadata_openclaw.get("requires"), dict)
        else {}
    )

    tools = _string_list(requires.get("tools"))
    bins = _string_list(requires.get("bins")) + _string_list(openclaw_requires.get("bins"))
    env = _string_list(requires.get("env")) + _string_list(openclaw_requires.get("env"))
    config = _string_list(openclaw_requires.get("config"))

    runtime_requires = (runtime_contract.get("runtime") or {}).get("requires")
    for token in _string_list(runtime_requires):
        normalized = token.replace("_", "-")
        if normalized not in tools:
            tools.append(normalized)

    return {
        "tools": _string_list(tools),
        "bins": _string_list(bins),
        "env": _string_list(env),
        "config": _string_list(config),
    }


def _requires_tokens(requires_detail: dict[str, list[str]]) -> list[str]:
    tokens: list[str] = []
    for key in ("tools", "bins", "env", "config"):
        for value in requires_detail.get(key) or []:
            token = f"{key}:{value}"
            if token not in tokens:
                tokens.append(token)
    return tokens


def _runtime_readiness(
    *,
    runtime_model: dict,
    plugin_capabilities: dict[str, list[str]],
    background_tasks_required: bool,
    subagents_required: bool,
) -> dict:
    capabilities = dict(runtime_model.get("capabilities") or {})
    supports_plugins = capabilities.get("supports_plugins") is True
    supports_background_tasks = capabilities.get("supports_background_tasks") is True
    supports_subagents = capabilities.get("supports_subagents") is True
    ready = (
        (supports_plugins or not plugin_capabilities)
        and (supports_background_tasks or not background_tasks_required)
        and (supports_subagents or not subagents_required)
    )

    if not supports_plugins and plugin_capabilities:
        status = "missing-plugin-support"
    elif not supports_background_tasks and background_tasks_required:
        status = "missing-background-task-support"
    elif not supports_subagents and subagents_required:
        status = "missing-subagent-support"
    else:
        status = "ready"

    return {
        "ready": ready,
        "supports_background_tasks": supports_background_tasks,
        "supports_plugins": supports_plugins,
        "supports_subagents": supports_subagents,
        "status": status,
    }


def _openclaw_runtime_payload(
    root: Path, entry: dict, meta: dict, requires: dict, runtime_model: dict
) -> dict:
    runtime_contract = _openclaw_runtime_contract(root, entry)
    runtime_contract_payload = dict(runtime_contract.get("runtime") or {})
    runtime_targets = _runtime_targets(runtime_model)
    install_targets = _install_targets_from_runtime(runtime_targets)
    openclaw_runtime = (
        meta.get("openclaw_runtime") if isinstance(meta.get("openclaw_runtime"), dict) else {}
    )
    workspace_scope = runtime_contract_payload.get("workspace_scope") or openclaw_runtime.get(
        "workspace_scope"
    )
    if not isinstance(workspace_scope, str) or workspace_scope not in {"workspace", "user"}:
        workspace_scope = "workspace"

    plugin_capabilities = normalize_plugin_capabilities(
        runtime_contract_payload.get("plugin_capabilities")
        or openclaw_runtime.get("plugin_capabilities")
    )
    background_tasks_required = _bool_required(openclaw_runtime.get("background_tasks"))
    subagents_required = _bool_required(openclaw_runtime.get("subagents"))
    requires_detail = _requires_detail(meta, requires, runtime_contract)

    skill_precedence = list(runtime_targets)
    for marker in ["bundled", "extra"]:
        if marker not in skill_precedence:
            skill_precedence.append(marker)

    legacy_agents = _string_list(entry.get("agent_compatible")) or _string_list(
        meta.get("agent_compatible")
    )
    if "openclaw" not in legacy_agents:
        legacy_agents.append("openclaw")

    return {
        "platform": "openclaw",
        "source_mode": runtime_contract.get("source_mode") or "metadata-only",
        "workspace_scope": workspace_scope,
        "workspace_targets": runtime_targets,
        "skill_precedence": skill_precedence,
        "install_targets": install_targets,
        "requires": requires_detail,
        "requires_tokens": _requires_tokens(requires_detail),
        "requires_detail": requires_detail,
        "plugin_capabilities": plugin_capabilities,
        "background_tasks": {"required": background_tasks_required},
        "subagents": {"required": subagents_required},
        "readiness": _runtime_readiness(
            runtime_model=runtime_model,
            plugin_capabilities=plugin_capabilities,
            background_tasks_required=background_tasks_required,
            subagents_required=subagents_required,
        ),
        "legacy_compatibility": {
            "agent_compatible": legacy_agents,
            "agent_compatible_deprecated": True,
        },
    }


def _openclaw_interop_payload(runtime_model: dict):
    return {
        "runtime_targets": _runtime_targets(runtime_model),
        "import_supported": True,
        "export_supported": True,
        "public_publish": {
            "clawhub": {
                "supported": True,
                "default": False,
            }
        },
    }


def build_ai_index(*, root: Path, catalog_entries: list, distribution_entries: list) -> dict:
    root = Path(root).resolve()
    runtime_model = _load_runtime_model(root)
    catalog_lookup = _catalog_entry_by_key(catalog_entries)
    grouped = {}
    for entry in distribution_entries or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("qualified_name") or entry.get("name")
        version = entry.get("version")
        if not key or not version:
            continue
        grouped.setdefault(key, []).append(entry)

    skills = []
    for key in sorted(grouped):
        versions = _sort_versions(item.get("version") for item in grouped[key])
        if not versions:
            continue
        current = catalog_lookup.get(key) or grouped[key][0]
        meta = _meta_for_entry(root, current)
        decision_metadata = canonical_decision_metadata(meta)
        publisher = _publisher_for_entry(current, meta)
        verified_support = current.get("verified_support") or {}
        requires = meta.get("requires") if isinstance(meta.get("requires"), dict) else {}
        entrypoints = meta.get("entrypoints") if isinstance(meta.get("entrypoints"), dict) else {}
        version_map = {}
        for dist in grouped[key]:
            version = dist.get("version")
            if not version:
                continue
            version_map[version] = {
                "manifest_path": dist.get("manifest_path"),
                "distribution_manifest_path": dist.get("manifest_path"),
                "bundle_path": dist.get("bundle_path"),
                "bundle_sha256": dist.get("bundle_sha256"),
                "attestation_path": dist.get("attestation_path"),
                "attestation_signature_path": dist.get("attestation_signature_path"),
                "published_at": dist.get("generated_at"),
                "stability": "stable",
                "installable": True,
                "attestation_formats": ["ssh", "ci"]
                if dist.get("ci_attestation_path")
                else ["ssh"],
                "trust_state": "verified" if dist.get("attestation_signature_path") else "attested",
                "resolution": {
                    "preferred_source": "distribution-manifest",
                    "fallback_allowed": False,
                },
            }
        latest_version = versions[0]
        latest_entry = version_map[latest_version]
        runtime_payload = _openclaw_runtime_payload(root, current, meta, requires, runtime_model)
        agent_compatible = _string_list(current.get("agent_compatible")) or _string_list(
            meta.get("agent_compatible")
        )
        if "openclaw" not in agent_compatible:
            agent_compatible.append("openclaw")
        skills.append(
            {
                "name": current.get("name"),
                "publisher": publisher,
                "qualified_name": current.get("qualified_name")
                or (
                    f"{publisher}/{current.get('name')}"
                    if publisher and current.get("name")
                    else current.get("name")
                ),
                "summary": current.get("summary") or "",
                "tags": meta.get("tags") or [],
                "maturity": decision_metadata["maturity"],
                "quality_score": decision_metadata["quality_score"],
                "capabilities": decision_metadata["capabilities"],
                "last_verified_at": _last_verified_at(verified_support, meta),
                "use_when": decision_metadata["use_when"],
                "avoid_when": decision_metadata["avoid_when"],
                "runtime_assumptions": decision_metadata["runtime_assumptions"],
                "runtime": runtime_payload,
                "agent_compatible": agent_compatible,
                "compatibility": {
                    "declared_support": current.get("declared_support")
                    or current.get("agent_compatible")
                    or agent_compatible,
                    "verified_support": verified_support,
                },
                "verified_support": verified_support,
                "trust_state": _trust_state_from_version_entry(latest_entry),
                "default_install_version": latest_version,
                "latest_version": latest_version,
                "available_versions": versions,
                "entrypoints": {
                    "skill_md": entrypoints.get("skill_md") or "SKILL.md",
                },
                "requires": {
                    "tools": requires.get("tools") or [],
                    "env": requires.get("env") or [],
                    "bins": requires.get("bins") or [],
                },
                "interop": {
                    "openclaw": _openclaw_interop_payload(runtime_model),
                },
                "versions": {version: version_map[version] for version in versions},
            }
        )

    default_registry = None
    for entry in catalog_entries or []:
        if isinstance(entry, dict) and entry.get("source_registry"):
            default_registry = entry.get("source_registry")
            break

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "registry": {
            "default_registry": default_registry,
        },
        "install_policy": dict(INSTALL_POLICY),
        "skills": skills,
    }


__all__ = [
    "INSTALL_POLICY",
    "SEMVER_RE",
    "build_ai_index",
]
