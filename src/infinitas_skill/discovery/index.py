import json
import re
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.install.http_registry import (
    HostedRegistryError,
    fetch_json,
    registry_catalog_path,
)
from infinitas_skill.install.registry_sources import normalized_auth, resolve_registry_root

from .ai_index import validate_ai_index_payload
from .decision_metadata import canonical_decision_metadata

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$")


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


def _relative_repo_path(value):
    if not isinstance(value, str) or not value.strip():
        return False
    return not Path(value).is_absolute()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_source_root(root: Path, reg: dict, reg_root: Path | None):
    if reg_root is None:
        return None
    if reg_root == root:
        return "."
    local_path = reg.get("local_path")
    if isinstance(local_path, str) and local_path.strip():
        candidate = Path(local_path.strip())
        if candidate.is_absolute():
            return str(candidate.resolve())
        return str(candidate)
    try:
        return str(reg_root.relative_to(root))
    except ValueError:
        return str(reg_root)


def normalize_discovery_skill(
    skill: dict,
    *,
    source_registry: str,
    source_priority: int,
    trust_level: str,
    default_registry: str,
) -> dict:
    decision_metadata = canonical_decision_metadata(skill)
    runtime = dict(skill.get("runtime") or {})
    readiness = dict(runtime.get("readiness") or {})
    runtime_readiness = readiness.get("status")
    if not isinstance(runtime_readiness, str) or not runtime_readiness.strip():
        runtime_readiness = "ready" if readiness.get("ready") is True else "unknown"
    install_targets = runtime.get("install_targets")
    install_targets = install_targets if isinstance(install_targets, dict) else {}
    workspace_targets = list(install_targets.get("workspace") or [])
    if not workspace_targets:
        workspace_targets = [
            target
            for target in list(runtime.get("workspace_targets") or [])
            if isinstance(target, str)
            and target
            and not target.startswith("~/")
            and not Path(target).is_absolute()
        ]
    legacy_agent_compatible = list(skill.get("agent_compatible") or [])
    if runtime.get("platform") == "openclaw" and readiness.get("ready") is True:
        if "openclaw" not in legacy_agent_compatible:
            legacy_agent_compatible.append("openclaw")
    qualified_name = skill.get("qualified_name") or skill.get("name")
    latest_version = skill.get("latest_version") or skill.get("default_install_version") or ""
    match_names = []
    for candidate in [skill.get("name"), qualified_name]:
        if isinstance(candidate, str) and candidate.strip() and candidate not in match_names:
            match_names.append(candidate)
    publisher = skill.get("publisher")
    if (
        isinstance(publisher, str)
        and publisher.strip()
        and isinstance(skill.get("name"), str)
        and skill.get("name").strip()
    ):
        qualified = f"{publisher.strip()}/{skill.get('name').strip()}"
        if qualified not in match_names:
            match_names.append(qualified)
    return {
        "name": skill.get("name"),
        "qualified_name": qualified_name,
        "publisher": publisher,
        "summary": skill.get("summary") or "",
        "source_registry": source_registry,
        "source_priority": source_priority,
        "match_names": sorted(match_names),
        "default_install_version": skill.get("default_install_version") or latest_version,
        "latest_version": latest_version,
        "available_versions": list(skill.get("available_versions") or []),
        "runtime": runtime,
        "runtime_readiness": runtime_readiness,
        "workspace_targets": workspace_targets,
        "agent_compatible": legacy_agent_compatible,
        "install_requires_confirmation": source_registry != default_registry,
        "trust_level": trust_level,
        "trust_state": skill.get("trust_state") or "unknown",
        "tags": list(skill.get("tags") or []),
        "maturity": decision_metadata["maturity"],
        "quality_score": decision_metadata["quality_score"],
        "last_verified_at": skill.get("last_verified_at")
        if isinstance(skill.get("last_verified_at"), str) and skill.get("last_verified_at").strip()
        else None,
        "capabilities": decision_metadata["capabilities"],
        "verified_support": dict(skill.get("verified_support") or {}),
        "attestation_formats": list(
            ((skill.get("versions") or {}).get(latest_version) or {}).get("attestation_formats")
            or ["ssh"]
        ),
        "use_when": decision_metadata["use_when"],
        "avoid_when": decision_metadata["avoid_when"],
        "runtime_assumptions": decision_metadata["runtime_assumptions"],
    }


def _sort_skills(skills):
    return sorted(
        skills,
        key=lambda item: (
            -(item.get("source_priority") or 0),
            item.get("qualified_name") or "",
            tuple(-part for part in _semver_key(item.get("latest_version"))[:4]),
            item.get("latest_version") or "",
        ),
    )


def build_discovery_index(*, root: Path, local_ai_index: dict, registry_config: dict) -> dict:
    root = Path(root).resolve()
    registries = registry_config.get("registries") or []
    default_registry = registry_config.get("default_registry")
    skills = []
    sources = []

    for reg in registries:
        if reg.get("enabled") is False:
            continue
        reg_name = reg.get("name")
        reg_root = resolve_registry_root(root, reg)
        use_local_payload = reg_root == root
        payload = local_ai_index if use_local_payload else None
        ai_index_path = (reg_root / "catalog" / "ai-index.json") if reg_root else None
        status = "ready" if payload else "missing-ai-index"
        if reg.get("kind") == "http":
            auth = normalized_auth(reg)
            try:
                payload = fetch_json(
                    reg.get("base_url"),
                    registry_catalog_path(reg, "ai_index"),
                    token_env=auth.get("env") if auth.get("mode") == "token" else None,
                )
                errors = validate_ai_index_payload(payload)
                status = "ready" if not errors else "invalid-ai-index"
                if errors:
                    payload = None
            except HostedRegistryError:
                payload = None
                status = "missing-ai-index"
        elif not use_local_payload and ai_index_path and ai_index_path.exists():
            try:
                payload = _load_json(ai_index_path)
                status = "ready"
            except Exception:
                payload = None
                status = "invalid-ai-index"

        source_entry = {
            "name": reg_name,
            "kind": reg.get("kind"),
            "priority": reg.get("priority", 0),
            "trust_level": reg.get("trust"),
            "root": _stable_source_root(root, reg, reg_root),
            "status": status,
        }
        if reg.get("kind") == "http":
            source_entry["base_url"] = reg.get("base_url")
        sources.append(source_entry)

        if not isinstance(payload, dict):
            continue
        for skill in payload.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            skills.append(
                normalize_discovery_skill(
                    skill,
                    source_registry=reg_name,
                    source_priority=reg.get("priority", 0),
                    trust_level=reg.get("trust"),
                    default_registry=default_registry,
                )
            )

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "default_registry": default_registry,
        "sources": sources,
        "resolution_policy": {
            "private_registry_first": True,
            "external_requires_confirmation": True,
            "auto_install_mutable_sources": False,
        },
        "skills": _sort_skills(skills),
    }


def validate_discovery_index_payload(payload: dict) -> list:
    errors = []
    if not isinstance(payload, dict):
        return ["discovery-index payload must be an object"]

    if payload.get("schema_version") != 1:
        errors.append("discovery-index schema_version must equal 1")
    if (
        not isinstance(payload.get("generated_at"), str)
        or not payload.get("generated_at", "").strip()
    ):
        errors.append("discovery-index generated_at must be a non-empty string")
    if (
        not isinstance(payload.get("default_registry"), str)
        or not payload.get("default_registry", "").strip()
    ):
        errors.append("discovery-index default_registry must be a non-empty string")

    sources = payload.get("sources")
    if not isinstance(sources, list):
        errors.append("discovery-index sources must be an array")

    resolution_policy = payload.get("resolution_policy")
    if not isinstance(resolution_policy, dict):
        errors.append("discovery-index resolution_policy must be an object")
    else:
        if resolution_policy.get("private_registry_first") is not True:
            errors.append("discovery-index resolution_policy.private_registry_first must be true")
        if resolution_policy.get("external_requires_confirmation") is not True:
            errors.append(
                "discovery-index resolution_policy.external_requires_confirmation must be true"
            )
        if resolution_policy.get("auto_install_mutable_sources") is not False:
            errors.append(
                "discovery-index resolution_policy.auto_install_mutable_sources must be false"
            )

    skills = payload.get("skills")
    if not isinstance(skills, list):
        errors.append("discovery-index skills must be an array")
        return errors

    for index, skill in enumerate(skills, start=1):
        prefix = f"discovery-index skills[{index}]"
        if not isinstance(skill, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "name",
            "qualified_name",
            "source_registry",
            "default_install_version",
            "latest_version",
        ]:
            if not isinstance(skill.get(field), str) or not skill.get(field, "").strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if not isinstance(skill.get("summary"), str):
            errors.append(f"{prefix}.summary must be a string")
        if not isinstance(skill.get("source_priority"), int):
            errors.append(f"{prefix}.source_priority must be an integer")
        if (
            not isinstance(skill.get("trust_level"), str)
            or not skill.get("trust_level", "").strip()
        ):
            errors.append(f"{prefix}.trust_level must be a non-empty string")
        if not isinstance(skill.get("install_requires_confirmation"), bool):
            errors.append(f"{prefix}.install_requires_confirmation must be a boolean")
        if skill.get("runtime_readiness") is not None and (
            not isinstance(skill.get("runtime_readiness"), str)
            or not skill.get("runtime_readiness", "").strip()
        ):
            errors.append(f"{prefix}.runtime_readiness must be a non-empty string when present")
        for field in [
            "match_names",
            "available_versions",
            "use_when",
            "avoid_when",
            "runtime_assumptions",
            "tags",
            "attestation_formats",
            "capabilities",
        ]:
            value = skill.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{prefix}.{field} must be an array of strings")
        if skill.get("workspace_targets") is not None:
            value = skill.get("workspace_targets")
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(
                    f"{prefix}.workspace_targets must be an array of strings when present"
                )
        if not isinstance(skill.get("maturity"), str) or not skill.get("maturity", "").strip():
            errors.append(f"{prefix}.maturity must be a non-empty string")
        if not isinstance(skill.get("quality_score"), int):
            errors.append(f"{prefix}.quality_score must be an integer")
        if skill.get("last_verified_at") is not None and (
            not isinstance(skill.get("last_verified_at"), str)
            or not skill.get("last_verified_at", "").strip()
        ):
            errors.append(f"{prefix}.last_verified_at must be a non-empty string when present")
        if (
            not isinstance(skill.get("trust_state"), str)
            or not skill.get("trust_state", "").strip()
        ):
            errors.append(f"{prefix}.trust_state must be a non-empty string")
        if not isinstance(skill.get("verified_support"), dict):
            errors.append(f"{prefix}.verified_support must be an object")
        runtime = skill.get("runtime")
        if runtime is not None:
            if not isinstance(runtime, dict):
                errors.append(f"{prefix}.runtime must be an object when present")
                continue
            if runtime.get("platform") != "openclaw":
                errors.append(f"{prefix}.runtime.platform must equal openclaw")
            for field in ["workspace_scope", "source_mode"]:
                value = runtime.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{prefix}.runtime.{field} must be a non-empty string")
            for field in ["workspace_targets", "skill_precedence"]:
                value = runtime.get(field)
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    errors.append(f"{prefix}.runtime.{field} must be an array of strings")
            install_targets = runtime.get("install_targets")
            if not isinstance(install_targets, dict):
                errors.append(f"{prefix}.runtime.install_targets must be an object")
            else:
                for field in ["workspace", "shared"]:
                    value = install_targets.get(field)
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        errors.append(
                            f"{prefix}.runtime.install_targets.{field} must be an array of strings"
                        )
            requires = runtime.get("requires")
            if not isinstance(requires, dict):
                errors.append(f"{prefix}.runtime.requires must be an object")
            else:
                for field in ["tools", "bins", "env", "config"]:
                    value = requires.get(field)
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        errors.append(
                            f"{prefix}.runtime.requires.{field} must be an array of strings"
                        )
            if not isinstance(runtime.get("plugin_capabilities"), dict):
                errors.append(f"{prefix}.runtime.plugin_capabilities must be an object")
            for field in ["background_tasks", "subagents", "legacy_compatibility"]:
                if not isinstance(runtime.get(field), dict):
                    errors.append(f"{prefix}.runtime.{field} must be an object")
            readiness = runtime.get("readiness")
            if not isinstance(readiness, dict):
                errors.append(f"{prefix}.runtime.readiness must be an object")
            else:
                if (
                    not isinstance(readiness.get("status"), str)
                    or not readiness.get("status", "").strip()
                ):
                    errors.append(f"{prefix}.runtime.readiness.status must be a non-empty string")
                for field in [
                    "ready",
                    "supports_background_tasks",
                    "supports_plugins",
                    "supports_subagents",
                ]:
                    if not isinstance(readiness.get(field), bool):
                        errors.append(f"{prefix}.runtime.readiness.{field} must be a boolean")
    return errors
