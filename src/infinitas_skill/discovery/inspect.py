"""Discovery inspect helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .inspect_memory import load_inspect_memory_hints
from .inspect_view import build_inspect_payload, dependency_summary, derive_trust_state
from .memory_audit import MemoryAuditRecorder, emit_inspect_memory_audit


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ai_index(root: Path):
    return _load_json(root / "catalog" / "ai-index.json")


def _load_distributions(root: Path):
    return _load_json(root / "catalog" / "distributions.json")


def _distribution_lookup(root: Path):
    payload = _load_distributions(root)
    lookup = {}
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        lookup[(item.get("qualified_name") or item.get("name"), item.get("version"))] = item
    return lookup


def _load_optional_json(root: Path, relative_path: str | None):
    if not isinstance(relative_path, str) or not relative_path.strip():
        return {}
    path = root / relative_path
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        return {}


def inspect_skill(
    root: Path,
    name: str,
    version: str | None = None,
    *,
    memory_provider: Any | None = None,
    memory_scope: dict | None = None,
    memory_context_enabled: bool = True,
    memory_top_k: int = 3,
    target_agent: str | None = None,
    audit_recorder: MemoryAuditRecorder | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    ai_index = _load_ai_index(root)
    distributions = _distribution_lookup(root)
    skill_entry = None
    for item in ai_index.get("skills") or []:
        if not isinstance(item, dict):
            continue
        if name in {item.get("qualified_name"), item.get("name")}:
            skill_entry = item
            break
    if skill_entry is None:
        raise ValueError(f"could not resolve skill {name!r}")

    resolved_version = (
        version or skill_entry.get("latest_version") or skill_entry.get("default_install_version")
    )
    version_entry = (skill_entry.get("versions") or {}).get(resolved_version) or {}
    distribution = distributions.get(
        (skill_entry.get("qualified_name") or skill_entry.get("name"), resolved_version),
        {},
    )
    manifest_path = (
        version_entry.get("distribution_manifest_path")
        or version_entry.get("manifest_path")
        or distribution.get("manifest_path")
    )
    provenance_path = version_entry.get("attestation_path") or distribution.get("attestation_path")
    manifest_payload = _load_optional_json(root, manifest_path)
    provenance_payload = _load_optional_json(root, provenance_path)
    verified_support = (skill_entry.get("compatibility") or {}).get("verified_support") or {}
    dependency_view = {
        "root": (manifest_payload.get("dependencies") or {}).get("root")
        or (distribution.get("dependencies") or {}).get("root")
        or {},
        "steps": (manifest_payload.get("dependencies") or {}).get("steps")
        or (distribution.get("dependencies") or {}).get("steps")
        or [],
    }
    dependency_view["summary"] = dependency_summary(
        {
            "root": dependency_view.get("root"),
            "steps": dependency_view.get("steps"),
            "registries_consulted": (manifest_payload.get("dependencies") or {}).get(
                "registries_consulted"
            )
            or (distribution.get("dependencies") or {}).get("registries_consulted")
            or [],
        }
    )
    required_formats = version_entry.get("attestation_formats") or [
        ((provenance_payload.get("attestation") or {}).get("format") or "ssh")
    ]
    trust_state = derive_trust_state(
        version_entry,
        manifest_payload,
        provenance_payload,
        distribution,
    )
    memory_hints = load_inspect_memory_hints(
        skill_ref=skill_entry.get("qualified_name") or skill_entry.get("name") or name,
        target_agent=target_agent,
        memory_provider=memory_provider,
        memory_scope=memory_scope,
        memory_context_enabled=memory_context_enabled,
        memory_top_k=memory_top_k,
    )
    provenance_view = {
        "attestation_path": provenance_path,
        "release_provenance_path": provenance_path,
        "attestation_signature_path": version_entry.get("attestation_signature_path")
        or distribution.get("attestation_signature_path"),
        "attestation_formats": required_formats,
        "required_attestation_formats": required_formats,
        "signer_identity": (
            (manifest_payload.get("attestation_bundle") or {}).get("signer_identity")
        )
        or ((provenance_payload.get("attestation") or {}).get("signer_identity")),
        "policy": {
            "policy_mode": ((provenance_payload.get("attestation") or {}).get("policy_mode")),
            "require_verified_attestation_for_release_output": (
                (provenance_payload.get("attestation") or {}).get(
                    "require_verified_attestation_for_release_output"
                )
            ),
            "require_verified_attestation_for_distribution": (
                (provenance_payload.get("attestation") or {}).get(
                    "require_verified_attestation_for_distribution"
                )
            ),
        },
    }
    distribution_view = {
        "manifest_path": manifest_path,
        "bundle_path": version_entry.get("bundle_path") or distribution.get("bundle_path"),
        "bundle_sha256": version_entry.get("bundle_sha256") or distribution.get("bundle_sha256"),
        "source_type": distribution.get("source_type") or "distribution-manifest",
        "bundle_size": distribution.get("bundle_size")
        or ((manifest_payload.get("bundle") or {}).get("size")),
        "bundle_file_count": distribution.get("bundle_file_count")
        or ((manifest_payload.get("bundle") or {}).get("file_count")),
    }
    trust_view = {
        "state": trust_state,
        "manifest_present": bool(manifest_path),
        "attestation_present": bool(provenance_path),
        "signature_present": bool(
            version_entry.get("attestation_signature_path")
            or ((manifest_payload.get("attestation_bundle") or {}).get("signature_path"))
        ),
        "required_attestation_formats": required_formats,
    }
    payload = build_inspect_payload(
        skill_entry=skill_entry,
        resolved_version=resolved_version,
        trust_state=trust_state,
        verified_support=verified_support,
        dependency_view=dependency_view,
        provenance_view=provenance_view,
        distribution_view=distribution_view,
        trust_view=trust_view,
        memory_hints=memory_hints,
    )
    emit_inspect_memory_audit(
        audit_recorder=audit_recorder,
        skill_ref=skill_entry.get("qualified_name") or skill_entry.get("name") or name,
        version=resolved_version,
        target_agent=target_agent,
        payload=payload,
    )
    return payload


__all__ = ["inspect_skill"]
