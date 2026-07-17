"""Discovery inspect helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .inspect_view import build_inspect_payload, dependency_summary, derive_trust_state

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ai_index(root: Path) -> dict[str, Any]:
    return _load_json(root / "catalog" / "ai-index.json")


def _load_distributions(root: Path) -> dict[str, Any]:
    return _load_json(root / "catalog" / "distributions.json")


def _distribution_lookup(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load_distributions(root)
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("qualified_name") or item.get("name")
        version = item.get("version")
        if isinstance(name, str) and isinstance(version, str):
            lookup[(name, version)] = item
    return lookup


def _load_optional_json(root: Path, relative_path: str | None) -> dict[str, Any]:
    if not isinstance(relative_path, str) or not relative_path.strip():
        return {}
    path = root / relative_path
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
    distributions = _distribution_lookup(root)
    skill_entry = _find_skill_entry(ai_index, name)

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
    manifest_payload = _load_optional_json(root, manifest_path)
    provenance_payload = _load_optional_json(root, provenance_path)
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
