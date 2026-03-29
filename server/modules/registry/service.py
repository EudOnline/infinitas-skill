from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from server.auth import AUTH_COOKIE_NAME
from server.modules.access.authn import AccessContext, resolve_access_context
from server.modules.access.authz import can_access_release
from server.modules.discovery.projections import DiscoveryProjection, build_release_projections

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

TOP_LEVEL_METADATA_PATHS = frozenset(
    {
        "ai-index.json",
        "discovery-index.json",
        "distributions.json",
        "compatibility.json",
    }
)


class RegistryError(Exception):
    pass


class UnauthorizedError(RegistryError):
    pass


class NotFoundError(RegistryError):
    pass


@dataclass(frozen=True)
class RegistryAudience:
    mode: str
    context: AccessContext | None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _resolve_request_token(request: Request) -> str | None:
    return _extract_bearer_token(request.headers.get("authorization")) or request.cookies.get(AUTH_COOKIE_NAME)


def _resolve_registry_audience(db: Session, request: Request) -> RegistryAudience:
    token = _resolve_request_token(request)
    if not token:
        return RegistryAudience(mode="public", context=None)

    context = resolve_access_context(db, token, allow_user_bridge=True)
    if context is None:
        raise UnauthorizedError("invalid registry bearer token")
    if context.credential.grant_id is not None:
        return RegistryAudience(mode="grant", context=context)
    return RegistryAudience(mode="me", context=context)


def _audience_rank(audience_type: str) -> int:
    return {
        "private": 4,
        "grant": 3,
        "authenticated": 2,
        "public": 1,
    }.get(str(audience_type or ""), 0)


def _version_sort_key(version: str) -> tuple[tuple[int, int], ...]:
    parts: list[tuple[int, int]] = []
    buffer = ""
    for char in str(version or ""):
        if char.isdigit():
            buffer += char
            continue
        if buffer:
            parts.append((0, int(buffer)))
            buffer = ""
        parts.append((1, ord(char)))
    if buffer:
        parts.append((0, int(buffer)))
    return tuple(parts)


def _entry_ready_key(entry: DiscoveryProjection) -> tuple[int, str]:
    if entry.ready_at is None:
        return (0, "")
    return (1, entry.ready_at.isoformat())


def _dedupe_entries(entries: list[DiscoveryProjection]) -> list[DiscoveryProjection]:
    by_release: dict[int, DiscoveryProjection] = {}
    for entry in entries:
        current = by_release.get(entry.release_id)
        if current is None or _audience_rank(entry.audience_type) > _audience_rank(current.audience_type):
            by_release[entry.release_id] = entry
    return sorted(
        by_release.values(),
        key=lambda entry: (
            entry.qualified_name,
            _version_sort_key(entry.version),
            _audience_rank(entry.audience_type),
            _entry_ready_key(entry),
        ),
        reverse=False,
    )


def _entry_is_materialized(entry: DiscoveryProjection) -> bool:
    required = [
        entry.manifest_path,
        entry.bundle_path,
        entry.provenance_path,
        entry.signature_path,
        entry.bundle_sha256,
    ]
    return all(isinstance(value, str) and value.strip() for value in required)


def _all_accessible_entries(db: Session, request: Request) -> list[DiscoveryProjection]:
    audience = _resolve_registry_audience(db, request)
    entries = [entry for entry in build_release_projections(db) if _entry_is_materialized(entry)]

    if audience.mode == "public":
        return _dedupe_entries([entry for entry in entries if entry.audience_type == "public"])

    context = audience.context
    if context is None:
        return []

    if audience.mode == "grant":
        return _dedupe_entries(
            [
                entry
                for entry in entries
                if entry.audience_type == "grant"
                and can_access_release(db, context=context, release_id=entry.release_id)
            ]
        )

    return _dedupe_entries(
        [
            entry
            for entry in entries
            if can_access_release(db, context=context, release_id=entry.release_id)
        ]
    )


def _listed_entries(db: Session, request: Request) -> list[DiscoveryProjection]:
    return [entry for entry in _all_accessible_entries(db, request) if entry.listing_mode == "listed"]


def _distribution_entry(entry: DiscoveryProjection) -> dict:
    return {
        "name": entry.name,
        "publisher": entry.publisher,
        "qualified_name": entry.qualified_name,
        "identity_mode": "qualified",
        "version": entry.version,
        "status": "active",
        "summary": entry.summary or "",
        "manifest_path": entry.manifest_path,
        "bundle_path": entry.bundle_path,
        "bundle_sha256": entry.bundle_sha256,
        "attestation_path": entry.provenance_path,
        "attestation_signature_path": entry.signature_path,
        "published_at": _iso(entry.ready_at) or _utc_now_iso(),
        "source_type": "private-release-manifest",
        "display_name": entry.display_name,
        "audience_type": entry.audience_type,
        "listing_mode": entry.listing_mode,
        "release_id": entry.release_id,
        "exposure_id": entry.exposure_id,
    }


def _skill_defaults(entry: dict) -> dict:
    return {
        "publisher": entry.get("publisher"),
        "summary": entry.get("summary") or "",
        "tags": [],
        "maturity": "stable",
        "quality_score": 0,
        "capabilities": [],
        "last_verified_at": entry.get("published_at"),
        "use_when": [],
        "avoid_when": [],
        "runtime_assumptions": [],
        "agent_compatible": [],
        "verified_support": {},
        "compatibility": {
            "declared_support": [],
            "verified_support": {},
        },
        "entrypoints": {"skill_md": "SKILL.md"},
        "requires": {"tools": [], "env": []},
        "interop": {"openclaw": dict(OPENCLAW_INTEROP)},
    }


def _build_ai_index_from_entries(entries: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        key = entry.get("qualified_name") or entry.get("name")
        if isinstance(key, str) and key:
            grouped.setdefault(key, []).append(entry)

    skills: list[dict] = []
    for key in sorted(grouped):
        version_map = {
            str(item.get("version")): item
            for item in grouped[key]
            if isinstance(item.get("version"), str) and item.get("version")
        }
        versions = sorted(version_map, key=_version_sort_key, reverse=True)
        if not versions:
            continue

        latest_version = versions[0]
        latest_entry = version_map[latest_version]
        defaults = _skill_defaults(latest_entry)

        skills.append(
            {
                "name": latest_entry.get("name"),
                "publisher": defaults["publisher"],
                "qualified_name": key,
                "summary": defaults["summary"],
                "tags": list(defaults["tags"]),
                "maturity": defaults["maturity"],
                "quality_score": defaults["quality_score"],
                "capabilities": list(defaults["capabilities"]),
                "last_verified_at": defaults["last_verified_at"],
                "use_when": list(defaults["use_when"]),
                "avoid_when": list(defaults["avoid_when"]),
                "runtime_assumptions": list(defaults["runtime_assumptions"]),
                "agent_compatible": list(defaults["agent_compatible"]),
                "compatibility": dict(defaults["compatibility"]),
                "verified_support": dict(defaults["verified_support"]),
                "trust_state": "private-first",
                "default_install_version": latest_version,
                "latest_version": latest_version,
                "available_versions": versions,
                "entrypoints": dict(defaults["entrypoints"]),
                "requires": {
                    "tools": list(defaults["requires"]["tools"]),
                    "env": list(defaults["requires"]["env"]),
                },
                "interop": {"openclaw": dict(defaults["interop"]["openclaw"])},
                "versions": {
                    version: {
                        "manifest_path": version_map[version]["manifest_path"],
                        "distribution_manifest_path": version_map[version]["manifest_path"],
                        "bundle_path": version_map[version]["bundle_path"],
                        "bundle_sha256": version_map[version]["bundle_sha256"],
                        "attestation_path": version_map[version]["attestation_path"],
                        "attestation_signature_path": version_map[version]["attestation_signature_path"],
                        "published_at": version_map[version]["published_at"],
                        "stability": "stable",
                        "installable": True,
                        "attestation_formats": ["private-first"],
                        "trust_state": "private-first",
                        "resolution": {
                            "preferred_source": "distribution-manifest",
                            "fallback_allowed": False,
                        },
                    }
                    for version in versions
                },
            }
        )

    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "registry": {
            "default_registry": "self",
        },
        "install_policy": dict(INSTALL_POLICY),
        "skills": skills,
    }


def build_registry_ai_index_payload(_settings, db: Session, request: Request) -> dict:
    entries = [_distribution_entry(entry) for entry in _all_accessible_entries(db, request)]
    return _build_ai_index_from_entries(entries)


def build_registry_distributions_payload(_settings, db: Session, request: Request) -> dict:
    entries = [_distribution_entry(entry) for entry in _all_accessible_entries(db, request)]
    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "skills": entries,
    }


def build_registry_discovery_payload(_settings, db: Session, request: Request) -> dict:
    entries = [_distribution_entry(entry) for entry in _listed_entries(db, request)]
    ai_payload = _build_ai_index_from_entries(entries)
    skills = []
    for skill in ai_payload.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        qualified_name = skill.get("qualified_name") or skill.get("name")
        name = skill.get("name")
        publisher = skill.get("publisher")
        match_names: list[str] = []
        for candidate in [name, qualified_name, f"{publisher}/{name}" if publisher and name else None]:
            if isinstance(candidate, str) and candidate and candidate not in match_names:
                match_names.append(candidate)
        latest_version = skill.get("latest_version") or skill.get("default_install_version")
        latest_version_payload = ((skill.get("versions") or {}).get(latest_version or "")) or {}
        skills.append(
            {
                "name": name,
                "qualified_name": qualified_name,
                "publisher": publisher,
                "summary": skill.get("summary") or "",
                "source_registry": "self",
                "source_priority": 100,
                "match_names": sorted(match_names),
                "default_install_version": skill.get("default_install_version"),
                "latest_version": latest_version,
                "available_versions": list(skill.get("available_versions") or []),
                "agent_compatible": list(skill.get("agent_compatible") or []),
                "install_requires_confirmation": False,
                "trust_level": "private",
                "trust_state": skill.get("trust_state") or "private-first",
                "tags": list(skill.get("tags") or []),
                "maturity": skill.get("maturity") or "stable",
                "quality_score": int(skill.get("quality_score") or 0),
                "last_verified_at": skill.get("last_verified_at"),
                "capabilities": list(skill.get("capabilities") or []),
                "verified_support": dict(skill.get("verified_support") or {}),
                "attestation_formats": list(latest_version_payload.get("attestation_formats") or ["private-first"]),
                "use_when": list(skill.get("use_when") or []),
                "avoid_when": list(skill.get("avoid_when") or []),
                "runtime_assumptions": list(skill.get("runtime_assumptions") or []),
            }
        )
    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "default_registry": "self",
        "sources": [
            {
                "name": "self",
                "kind": "http",
                "priority": 100,
                "trust_level": "private",
                "root": ".",
                "status": "ready",
                "base_url": None,
            }
        ],
        "resolution_policy": {
            "private_registry_first": True,
            "external_requires_confirmation": True,
            "auto_install_mutable_sources": False,
        },
        "skills": skills,
    }


def build_registry_compatibility_payload(_settings, db: Session, request: Request) -> dict:
    entries = [_distribution_entry(entry) for entry in _all_accessible_entries(db, request)]
    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "skills": [
            {
                "qualified_name": entry["qualified_name"],
                "name": entry["name"],
                "publisher": entry["publisher"],
                "version": entry["version"],
                "bundle_sha256": entry["bundle_sha256"],
            }
            for entry in entries
        ],
    }


def _entry_registry_paths(entry: DiscoveryProjection) -> dict[str, str]:
    provenance_filename = Path(entry.provenance_path).name
    signature_filename = Path(entry.signature_path).name
    return {
        entry.manifest_path: entry.manifest_path,
        entry.bundle_path: entry.bundle_path,
        entry.provenance_path: entry.provenance_path,
        entry.signature_path: entry.signature_path,
        f"catalog/distributions/{entry.publisher}/{entry.name}/{entry.version}/manifest.json": entry.manifest_path,
        f"catalog/distributions/{entry.publisher}/{entry.name}/{entry.version}/skill.tar.gz": entry.bundle_path,
        f"catalog/provenance/{provenance_filename}": entry.provenance_path,
        f"catalog/provenance/{signature_filename}": entry.signature_path,
        f"provenance/{provenance_filename}": entry.provenance_path,
        f"provenance/{signature_filename}": entry.signature_path,
    }


def resolve_registry_artifact_relative_path(_settings, db: Session, request: Request, registry_path: str) -> str:
    normalized = str(registry_path or "").strip().strip("/")
    if not normalized or normalized in TOP_LEVEL_METADATA_PATHS:
        raise NotFoundError("registry artifact not found")

    allowed_paths: dict[str, str] = {}
    for entry in _all_accessible_entries(db, request):
        allowed_paths.update(_entry_registry_paths(entry))

    resolved = allowed_paths.get(normalized)
    if resolved is None:
        raise NotFoundError("registry artifact not found")
    return resolved
