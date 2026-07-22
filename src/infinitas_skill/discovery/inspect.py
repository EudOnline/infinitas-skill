"""Discovery inspect helpers."""

from __future__ import annotations

import json
import logging
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
from infinitas_skill.install.registry_sources import find_registry, load_registry_config

from .inspect_view import build_inspect_payload, dependency_summary, derive_trust_state

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ai_index(root: Path) -> dict[str, Any]:
    discovery_index = root / "catalog" / "discovery-index.json"
    selected = discovery_index if discovery_index.exists() else root / "catalog" / "ai-index.json"
    return _load_json(selected)


def _registry_for_skill(root: Path, skill_entry: dict[str, Any]) -> dict[str, Any] | None:
    source_registry = skill_entry.get("source_registry")
    if not isinstance(source_registry, str) or not source_registry.strip():
        return None
    try:
        return find_registry(load_registry_config(root), source_registry)
    except Exception:
        logger.debug("failed to resolve source registry %s", source_registry)
        return None


def _http_token_env(registry: dict[str, Any]) -> str | None:
    auth = normalized_auth(registry)
    return auth.get("env") if auth.get("mode") == "token" else None


def _http_base_url(registry: dict[str, Any]) -> str:
    value = registry.get("base_url")
    if not isinstance(value, str) or not value.strip():
        raise HostedRegistryError("hosted registry is missing base_url")
    return value


def _load_distributions(root: Path, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    if registry and registry.get("kind") == "http":
        try:
            return fetch_json(
                _http_base_url(registry),
                registry_catalog_path(registry, "distributions"),
                token_env=_http_token_env(registry),
            )
        except HostedRegistryError:
            cached = (
                root
                / ".cache"
                / "registries"
                / str(registry.get("name"))
                / "catalog"
                / Path(registry_catalog_path(registry, "distributions")).name
            )
            if cached.exists():
                return _load_json(cached)
            raise
    if registry:
        registry_root = resolve_registry_root(root, registry)
        if registry_root and registry_root != root:
            candidate = registry_root / "catalog" / "distributions.json"
            if candidate.exists():
                return _load_json(candidate)
    return _load_json(root / "catalog" / "distributions.json")


def _distribution_lookup(
    root: Path, registry: dict[str, Any] | None = None
) -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load_distributions(root, registry)
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("qualified_name") or item.get("name")
        version = item.get("version")
        if isinstance(name, str) and isinstance(version, str):
            lookup[(name, version)] = item
    return lookup


def _load_optional_json(
    root: Path,
    relative_path: str | None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(relative_path, str) or not relative_path.strip():
        return {}
    path = root / relative_path
    if not path.exists():
        if registry and registry.get("kind") == "http":
            try:
                return fetch_json(
                    _http_base_url(registry),
                    relative_path,
                    token_env=_http_token_env(registry),
                )
            except HostedRegistryError:
                logger.debug("failed to fetch hosted JSON: %s", relative_path)
        elif registry:
            registry_root = resolve_registry_root(root, registry)
            if registry_root:
                path = registry_root / relative_path
        if not path.exists():
            return {}
    try:
        return _load_json(path)
    except Exception:
        logger.debug("failed to load optional JSON: %s", path)
        return {}


def _find_skill_entry(ai_index: dict, name: str) -> dict:
    for item in ai_index.get("skills") or []:
        if isinstance(item, dict) and name in {item.get("qualified_name"), item.get("name")}:
            return item
    raise ValueError(f"could not resolve skill {name!r}")


def _dependency_view(manifest: dict, distribution: dict) -> dict:
    manifest_dependencies = manifest.get("dependencies") or {}
    distribution_dependencies = distribution.get("dependencies") or {}
    view = {
        "root": manifest_dependencies.get("root") or distribution_dependencies.get("root") or {},
        "steps": manifest_dependencies.get("steps") or distribution_dependencies.get("steps") or [],
    }
    view["summary"] = dependency_summary(
        {
            **view,
            "registries_consulted": manifest_dependencies.get("registries_consulted")
            or distribution_dependencies.get("registries_consulted")
            or [],
        }
    )
    return view


def _provenance_view(
    version_entry: dict,
    distribution: dict,
    manifest: dict,
    provenance: dict,
    provenance_path: str | None,
    required_formats: list,
) -> dict:
    attestation = provenance.get("attestation") or {}
    return {
        "attestation_path": provenance_path,
        "release_provenance_path": provenance_path,
        "attestation_signature_path": version_entry.get("attestation_signature_path")
        or distribution.get("attestation_signature_path"),
        "attestation_formats": required_formats,
        "required_attestation_formats": required_formats,
        "signer_identity": (manifest.get("attestation_bundle") or {}).get("signer_identity")
        or attestation.get("signer_identity"),
        "policy": {
            "policy_mode": attestation.get("policy_mode"),
            "require_verified_attestation_for_release_output": attestation.get(
                "require_verified_attestation_for_release_output"
            ),
            "require_verified_attestation_for_distribution": attestation.get(
                "require_verified_attestation_for_distribution"
            ),
        },
    }


def _artifact_views(
    version_entry: dict,
    distribution: dict,
    manifest: dict,
    manifest_path: str | None,
    provenance_path: str | None,
    trust_state: str,
    required_formats: list,
) -> tuple[dict, dict]:
    bundle = manifest.get("bundle") or {}
    distribution_view = {
        "manifest_path": manifest_path,
        "bundle_path": version_entry.get("bundle_path") or distribution.get("bundle_path"),
        "bundle_sha256": version_entry.get("bundle_sha256") or distribution.get("bundle_sha256"),
        "source_type": distribution.get("source_type") or "distribution-manifest",
        "bundle_size": distribution.get("bundle_size") or bundle.get("size"),
        "bundle_file_count": distribution.get("bundle_file_count") or bundle.get("file_count"),
    }
    trust_view = {
        "state": trust_state,
        "manifest_present": bool(manifest_path),
        "attestation_present": bool(provenance_path),
        "signature_present": bool(
            version_entry.get("attestation_signature_path")
            or (manifest.get("attestation_bundle") or {}).get("signature_path")
        ),
        "required_attestation_formats": required_formats,
    }
    return distribution_view, trust_view


def _apply_runtime_view(payload: dict, skill_entry: dict) -> None:
    runtime = dict(skill_entry.get("runtime") or {})
    readiness = dict(runtime.get("readiness") or {})
    readiness_status = readiness.get("status")
    if not isinstance(readiness_status, str) or not readiness_status.strip():
        readiness_status = "ready" if readiness.get("ready") is True else "unknown"
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
    payload.update(
        {
            "runtime": runtime,
            "runtime_readiness": readiness_status,
            "workspace_fit": {
                "scope": runtime.get("workspace_scope") or "workspace",
                "status": "workspace-targets-declared"
                if workspace_targets
                else "workspace-targets-unknown",
                "targets": workspace_targets,
            },
            "plugin_needs": {"required": dict(runtime.get("plugin_capabilities") or {})},
            "background_tasks": dict(runtime.get("background_tasks") or {"required": False}),
            "subagents": dict(runtime.get("subagents") or {"required": False}),
        }
    )


def inspect_skill(
    root: Path,
    name: str,
    version: str | None = None,
    *,
    target_agent: str | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    ai_index = _load_ai_index(root)
    skill_entry = _find_skill_entry(ai_index, name)
    registry = _registry_for_skill(root, skill_entry)
    distributions = _distribution_lookup(root, registry)

    resolved_version = str(
        version
        or skill_entry.get("latest_version")
        or skill_entry.get("default_install_version")
        or ""
    )
    version_entry = (skill_entry.get("versions") or {}).get(resolved_version) or {}
    distribution_name = skill_entry.get("qualified_name") or skill_entry.get("name")
    distribution = (
        distributions.get((distribution_name, resolved_version), {})
        if isinstance(distribution_name, str)
        else {}
    )
    manifest_path = (
        version_entry.get("distribution_manifest_path")
        or version_entry.get("manifest_path")
        or distribution.get("manifest_path")
    )
    provenance_path = version_entry.get("attestation_path") or distribution.get("attestation_path")
    manifest_payload = _load_optional_json(root, manifest_path, registry)
    provenance_payload = _load_optional_json(root, provenance_path, registry)
    dependency_view = _dependency_view(manifest_payload, distribution)
    required_formats = version_entry.get("attestation_formats") or [
        ((provenance_payload.get("attestation") or {}).get("format") or "ssh")
    ]
    trust_state = derive_trust_state(
        version_entry,
        manifest_payload,
        provenance_payload,
        distribution,
    )
    provenance_view = _provenance_view(
        version_entry,
        distribution,
        manifest_payload,
        provenance_payload,
        provenance_path,
        required_formats,
    )
    distribution_view, trust_view = _artifact_views(
        version_entry,
        distribution,
        manifest_payload,
        manifest_path,
        provenance_path,
        trust_state,
        required_formats,
    )
    payload = build_inspect_payload(
        skill_entry=skill_entry,
        resolved_version=resolved_version,
        trust_state=trust_state,
        dependency_view=dependency_view,
        provenance_view=provenance_view,
        distribution_view=distribution_view,
        trust_view=trust_view,
    )
    _apply_runtime_view(payload, skill_entry)
    return payload


__all__ = ["inspect_skill"]
