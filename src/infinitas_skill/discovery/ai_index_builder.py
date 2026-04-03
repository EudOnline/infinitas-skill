from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .decision_metadata import canonical_decision_metadata

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$")

INSTALL_POLICY = {
    "mode": "immutable-only",
    "direct_source_install_allowed": False,
    "require_attestation": True,
    "require_sha256": True,
}

OPENCLAW_INTEROP = {
    "runtime_targets": ["~/.openclaw/skills", "~/.openclaw/workspace/skills"],
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


def _openclaw_interop_payload():
    return {
        "runtime_targets": list(OPENCLAW_INTEROP["runtime_targets"]),
        "import_supported": True,
        "export_supported": True,
        "public_publish": {
            "clawhub": {
                "supported": True,
                "default": False,
            }
        },
    }


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


def build_ai_index(*, root: Path, catalog_entries: list, distribution_entries: list) -> dict:
    root = Path(root).resolve()
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
                "agent_compatible": current.get("agent_compatible") or [],
                "compatibility": {
                    "declared_support": current.get("declared_support")
                    or current.get("agent_compatible")
                    or [],
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
                },
                "interop": {
                    "openclaw": _openclaw_interop_payload(),
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
    "OPENCLAW_INTEROP",
    "SEMVER_RE",
    "build_ai_index",
]
