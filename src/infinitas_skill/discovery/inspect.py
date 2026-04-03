"""Discovery inspect helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.memory import build_inspect_memory_query, trim_memory_records
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult

from .decision_metadata import canonical_decision_metadata

INSPECT_MEMORY_TYPES = {"experience", "task_context"}


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


def _compatibility_summary(verified_support: dict) -> dict:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("state"), str)
            and payload.get("state").strip()
        ):
            summary[platform] = payload.get("state")
    return summary


def _compatibility_freshness_summary(verified_support: dict) -> dict:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("freshness_state"), str)
            and payload.get("freshness_state").strip()
        ):
            summary[platform] = payload.get("freshness_state")
    return summary


def _dependency_summary(dependencies: dict) -> dict:
    root = dependencies.get("root") if isinstance(dependencies, dict) else {}
    steps = dependencies.get("steps") if isinstance(dependencies, dict) else []
    registries = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        registry = step.get("registry")
        if isinstance(registry, str) and registry not in registries:
            registries.append(registry)
    return {
        "root_name": (root or {}).get("name"),
        "root_source_type": (root or {}).get("source_type"),
        "step_count": len(steps or []),
        "registries_consulted": registries
        or list((dependencies.get("registries_consulted") or [])),
    }


def _derive_trust_state(
    version_entry: dict,
    manifest_payload: dict,
    provenance_payload: dict,
    distribution: dict,
) -> str:
    signature_present = bool(
        version_entry.get("attestation_signature_path")
        or ((manifest_payload.get("attestation_bundle") or {}).get("signature_path"))
    )
    attestation_present = bool(
        version_entry.get("attestation_path")
        or ((manifest_payload.get("attestation_bundle") or {}).get("provenance_path"))
    )
    policy = (
        (provenance_payload.get("attestation") or {})
        if isinstance(provenance_payload, dict)
        else {}
    )
    if (
        signature_present
        and policy.get("require_verified_attestation_for_distribution") is not False
    ):
        return "verified"
    if attestation_present:
        return "attested"
    if (
        distribution.get("manifest_path")
        or version_entry.get("distribution_manifest_path")
        or version_entry.get("manifest_path")
    ):
        return "installable"
    return version_entry.get("trust_state") or "unknown"


def _coerce_memory_search_result(
    payload: Any,
    *,
    fallback_backend: str,
) -> MemorySearchResult:
    if isinstance(payload, MemorySearchResult):
        return payload
    if not isinstance(payload, dict):
        return MemorySearchResult(records=[], backend=fallback_backend)

    backend = fallback_backend
    backend_value = payload.get("backend")
    if isinstance(backend_value, str) and backend_value.strip():
        backend = backend_value.strip()

    records = []
    raw_records = payload.get("records")
    if isinstance(raw_records, list):
        for item in raw_records:
            if isinstance(item, MemoryRecord):
                records.append(item)
                continue
            if not isinstance(item, dict):
                continue
            memory = item.get("memory")
            if not isinstance(memory, str) or not memory.strip():
                continue
            records.append(
                MemoryRecord(
                    memory=memory.strip(),
                    memory_type=(
                        item.get("memory_type")
                        if isinstance(item.get("memory_type"), str)
                        and item.get("memory_type", "").strip()
                        else "generic"
                    ),
                    score=(
                        float(item.get("score"))
                        if isinstance(item.get("score"), (int, float))
                        else None
                    ),
                    source=(
                        item.get("source")
                        if isinstance(item.get("source"), str) and item.get("source", "").strip()
                        else None
                    ),
                    metadata=(
                        item.get("metadata")
                        if isinstance(item.get("metadata"), dict)
                        else {}
                    ),
                )
            )
    return MemorySearchResult(records=records, backend=backend)


def _memory_hint_item(record: MemoryRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "memory_type": record.memory_type,
        "memory": record.memory,
    }
    if isinstance(record.score, (int, float)):
        payload["score"] = float(record.score)
    return payload


def _load_memory_hints(
    *,
    skill_ref: str,
    target_agent: str | None,
    memory_provider: Any | None,
    memory_scope: dict | None,
    memory_context_enabled: bool,
    memory_top_k: int,
) -> dict[str, Any]:
    backend = getattr(memory_provider, "backend_name", "disabled")
    base = {
        "used": False,
        "backend": backend if memory_provider is not None else "disabled",
        "matched_count": 0,
        "items": [],
        "advisory_only": True,
    }
    if memory_provider is None or not memory_context_enabled:
        base["status"] = "disabled"
        return base

    capabilities = getattr(memory_provider, "capabilities", {})
    if not isinstance(capabilities, dict) or not capabilities.get("read"):
        base["status"] = "unavailable"
        return base

    memory_scope = memory_scope if isinstance(memory_scope, dict) else {}
    query = build_inspect_memory_query(
        skill_ref=skill_ref,
        target_agent=target_agent,
        user_ref=memory_scope.get("user_ref"),
        principal_ref=memory_scope.get("principal_ref"),
        task=memory_scope.get("task_ref") or "inspect",
    )
    provider_scope = dict(query.provider_scope)
    for key in ["user_id", "agent_id", "run_id", "namespace"]:
        value = memory_scope.get(key)
        if isinstance(value, str) and value.strip():
            provider_scope[key] = value.strip()
    limit = (
        memory_top_k
        if isinstance(memory_top_k, int) and memory_top_k > 0
        else query.max_results
    )
    try:
        payload = memory_provider.search(
            query=query.query,
            limit=limit,
            scope=provider_scope,
            memory_types=query.memory_types,
        )
    except Exception as exc:
        base["status"] = "error"
        base["error"] = f"memory retrieval failed: {exc}"
        return base

    normalized = _coerce_memory_search_result(payload, fallback_backend=backend)
    filtered = [
        record
        for record in normalized.records
        if isinstance(record.memory_type, str) and record.memory_type in INSPECT_MEMORY_TYPES
    ]
    trimmed = trim_memory_records(filtered, max_items=limit, max_chars=180)
    base["backend"] = normalized.backend
    base["matched_count"] = len(filtered)
    base["items"] = [_memory_hint_item(record) for record in trimmed]
    base["used"] = bool(base["items"])
    base["status"] = "matched" if filtered else "no-match"
    return base


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
) -> dict:
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
    dependency_view["summary"] = _dependency_summary(
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
    trust_state = _derive_trust_state(
        version_entry, manifest_payload, provenance_payload, distribution
    )
    memory_hints = _load_memory_hints(
        skill_ref=skill_entry.get("qualified_name") or skill_entry.get("name") or name,
        target_agent=target_agent,
        memory_provider=memory_provider,
        memory_scope=memory_scope,
        memory_context_enabled=memory_context_enabled,
        memory_top_k=memory_top_k,
    )
    return {
        "ok": True,
        "name": skill_entry.get("name"),
        "qualified_name": skill_entry.get("qualified_name"),
        "publisher": skill_entry.get("publisher"),
        "version": resolved_version,
        "latest_version": skill_entry.get("latest_version"),
        "trust_state": trust_state,
        "decision_metadata": canonical_decision_metadata(skill_entry),
        "compatibility": {
            "declared_support": (
                (skill_entry.get("compatibility") or {}).get("declared_support") or []
            ),
            "verified_support": verified_support,
            "verified_summary": _compatibility_summary(verified_support),
            "freshness_summary": _compatibility_freshness_summary(verified_support),
        },
        "dependencies": dependency_view,
        "provenance": {
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
        },
        "distribution": {
            "manifest_path": manifest_path,
            "bundle_path": version_entry.get("bundle_path") or distribution.get("bundle_path"),
            "bundle_sha256": version_entry.get("bundle_sha256")
            or distribution.get("bundle_sha256"),
            "source_type": distribution.get("source_type") or "distribution-manifest",
            "bundle_size": distribution.get("bundle_size")
            or ((manifest_payload.get("bundle") or {}).get("size")),
            "bundle_file_count": distribution.get("bundle_file_count")
            or ((manifest_payload.get("bundle") or {}).get("file_count")),
        },
        "trust": {
            "state": trust_state,
            "manifest_present": bool(manifest_path),
            "attestation_present": bool(provenance_path),
            "signature_present": bool(
                version_entry.get("attestation_signature_path")
                or ((manifest_payload.get("attestation_bundle") or {}).get("signature_path"))
            ),
            "required_attestation_formats": required_formats,
        },
        "memory_hints": memory_hints,
    }


__all__ = ["inspect_skill"]
