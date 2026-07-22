import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.install.http_registry import (
    HostedRegistryError,
    fetch_json,
    registry_catalog_path,
)
from infinitas_skill.install.registry_source_primitives import (
    normalized_auth,
    resolve_registry_root,
)

from .ai_index import validate_ai_index_payload
from .decision_metadata import canonical_decision_metadata
from .primitives import semver_key


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative_repo_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return not Path(value).is_absolute()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_source_root(root: Path, reg: dict[str, Any], reg_root: Path | None) -> str | None:
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


def _runtime_projection(skill: dict) -> tuple[dict, str, list[str], list[str]]:
    runtime = dict(skill.get("runtime") or {})
    readiness = dict(runtime.get("readiness") or {})
    status = readiness.get("status")
    runtime_readiness = (
        status
        if isinstance(status, str) and status.strip()
        else "ready"
        if readiness.get("ready") is True
        else "unknown"
    )
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
    compatible_agents = list(skill.get("agent_compatible") or [])
    if (
        runtime.get("platform") == "openclaw"
        and readiness.get("ready") is True
        and "openclaw" not in compatible_agents
    ):
        compatible_agents.append("openclaw")
    return runtime, runtime_readiness, workspace_targets, compatible_agents


def _identity_projection(skill: dict) -> tuple[object, object, object, list[str]]:
    name = skill.get("name")
    qualified_name = skill.get("qualified_name") or name
    publisher = skill.get("publisher")
    match_names = [
        candidate
        for candidate in [name, qualified_name]
        if isinstance(candidate, str) and candidate.strip()
    ]
    if isinstance(publisher, str) and publisher.strip() and isinstance(name, str) and name.strip():
        match_names.append(f"{publisher.strip()}/{name.strip()}")
    return name, qualified_name, publisher, sorted(set(match_names))


def _version_projection(skill: dict) -> tuple[object, list[str]]:
    latest_version = skill.get("latest_version") or skill.get("default_install_version") or ""
    formats = list(
        ((skill.get("versions") or {}).get(latest_version) or {}).get("attestation_formats")
        or ["ssh"]
    )
    return latest_version, formats


def normalize_discovery_skill(
    skill: dict,
    *,
    source_registry: str,
    source_priority: int,
    trust_level: str,
    default_registry: str,
) -> dict:
    decision_metadata = canonical_decision_metadata(skill)
    runtime, runtime_readiness, workspace_targets, compatible_agents = _runtime_projection(skill)
    name, qualified_name, publisher, match_names = _identity_projection(skill)
    latest_version, attestation_formats = _version_projection(skill)
    last_verified_at = skill.get("last_verified_at")
    return {
        "name": skill.get("name"),
        "kind": skill.get("kind") or "skill",
        "qualified_name": qualified_name,
        "publisher": publisher,
        "summary": skill.get("summary") or "",
        "source_registry": source_registry,
        "source_priority": source_priority,
        "match_names": sorted(match_names),
        "default_install_version": skill.get("default_install_version") or latest_version,
        "latest_version": latest_version,
        "available_versions": list(skill.get("available_versions") or []),
        "versions": dict(skill.get("versions") or {}),
        "runtime": runtime,
        "runtime_readiness": runtime_readiness,
        "workspace_targets": workspace_targets,
        "agent_compatible": compatible_agents,
        "install_requires_confirmation": source_registry != default_registry,
        "trust_level": trust_level,
        "trust_state": skill.get("trust_state") or "unknown",
        "tags": list(skill.get("tags") or []),
        "maturity": decision_metadata["maturity"],
        "quality_score": decision_metadata["quality_score"],
        "last_verified_at": last_verified_at
        if isinstance(last_verified_at, str) and last_verified_at.strip()
        else None,
        "capabilities": decision_metadata["capabilities"],
        "verified_support": dict(skill.get("verified_support") or {}),
        "attestation_formats": attestation_formats,
        "use_when": decision_metadata["use_when"],
        "avoid_when": decision_metadata["avoid_when"],
        "runtime_assumptions": decision_metadata["runtime_assumptions"],
    }


def _sort_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        skills,
        key=lambda item: (
            -(item.get("source_priority") or 0),
            item.get("qualified_name") or "",
            tuple(-part for part in semver_key(item.get("latest_version"))[:4]),
            item.get("latest_version") or "",
        ),
    )


def build_discovery_index(*, root: Path, local_ai_index: dict, registry_config: dict) -> dict:
    root = Path(root).resolve()
    registries = registry_config.get("registries") or []
    default_registry = str(registry_config.get("default_registry") or "self")
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
    from .discovery_index_validation import validate_discovery_index_payload

    return validate_discovery_index_payload(payload)
