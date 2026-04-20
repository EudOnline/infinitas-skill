from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.access.authz import can_access_release
from server.modules.discovery import search
from server.modules.discovery.projections import (
    DiscoveryProjection,
    build_release_projections,
    projection_has_materialized_artifacts,
)
from server.settings import get_settings


class DiscoveryError(Exception):
    pass


class NotFoundError(DiscoveryError):
    pass


class ForbiddenError(DiscoveryError):
    pass


class ConflictError(DiscoveryError):
    pass


_VERSION_PARTS_RE = re.compile(r"(\d+|[A-Za-z]+)")


def _version_sort_key(version: str) -> tuple:
    parts = []
    for item in _VERSION_PARTS_RE.findall(str(version or "")):
        if item.isdigit():
            parts.append((0, int(item)))
        else:
            parts.append((1, item.lower()))
    return tuple(parts)


def _audience_rank(audience_type: str) -> int:
    return {
        "private": 4,
        "grant": 3,
        "authenticated": 2,
        "public": 1,
    }.get(str(audience_type or ""), 0)


def _ready_sort_key(value: datetime | None) -> tuple[int, str]:
    if value is None:
        return (0, "")
    return (1, value.isoformat())


def _dedupe(entries: list[DiscoveryProjection]) -> list[DiscoveryProjection]:
    by_release: dict[int, DiscoveryProjection] = {}
    for entry in entries:
        current = by_release.get(entry.release_id)
        if current is None or (
            _audience_rank(entry.audience_type) > _audience_rank(current.audience_type)
        ):
            by_release[entry.release_id] = entry
    return sorted(
        by_release.values(),
        key=lambda entry: (
            entry.qualified_name,
            _version_sort_key(entry.version),
            _audience_rank(entry.audience_type),
        ),
        reverse=False,
    )


def _match_base(entry: DiscoveryProjection, base_ref: str) -> bool:
    return base_ref == entry.name or base_ref == entry.qualified_name


def _parse_skill_ref(skill_ref: str) -> tuple[str, str | None]:
    raw = str(skill_ref or "").strip().strip("/")
    if not raw:
        raise NotFoundError("skill ref is required")
    if "@" in raw:
        base_ref, version = raw.rsplit("@", 1)
        return base_ref.strip(), version.strip() or None
    return raw, None


def _filter_install_candidates(
    entries: list[DiscoveryProjection], skill_ref: str
) -> list[DiscoveryProjection]:
    base_ref, requested_version = _parse_skill_ref(skill_ref)
    matches = [entry for entry in entries if _match_base(entry, base_ref)]
    if requested_version is not None:
        matches = [entry for entry in matches if entry.version == requested_version]
    return matches


def _resolve_install_candidate(
    entries: list[DiscoveryProjection], skill_ref: str
) -> DiscoveryProjection:
    matches = _filter_install_candidates(entries, skill_ref)
    if not matches:
        raise NotFoundError("install target not found")

    base_ref, requested_version = _parse_skill_ref(skill_ref)
    if "/" not in base_ref:
        qualified_names = sorted({entry.qualified_name for entry in matches})
        if len(qualified_names) > 1:
            raise ConflictError("ambiguous short skill ref")

    if requested_version is None:
        matches = sorted(
            matches,
            key=lambda entry: (
                _version_sort_key(entry.version),
                _ready_sort_key(entry.ready_at),
                _audience_rank(entry.audience_type),
            ),
            reverse=True,
        )
        return matches[0]

    matches = sorted(
        matches,
        key=lambda entry: (_audience_rank(entry.audience_type), _ready_sort_key(entry.ready_at)),
        reverse=True,
    )
    return matches[0]


def _ensure_user_context(context: AccessContext) -> None:
    if context.user is None or context.principal is None:
        raise ForbiddenError("user session required")


def _ensure_grant_context(context: AccessContext) -> None:
    if context.credential.grant_id is None:
        raise ForbiddenError("grant credential required")


_CATALOG_MAX_ENTRIES = 500


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _catalog_snapshot_roots() -> list[Path]:
    settings = get_settings()
    return [
        settings.artifact_path,
        settings.artifact_path / "catalog",
    ]


def _load_catalog_snapshot_skill_entries() -> list[dict]:
    for root in _catalog_snapshot_roots():
        payload = _read_json(root / "discovery-index.json")
        skills = payload.get("skills")
        if isinstance(skills, list):
            return [item for item in skills if isinstance(item, dict)]
    return []


def _load_catalog_distribution_entries() -> list[dict]:
    for root in _catalog_snapshot_roots():
        payload = _read_json(root / "distributions.json")
        skills = payload.get("skills")
        if isinstance(skills, list):
            return [item for item in skills if isinstance(item, dict)]
    return []


def _snapshot_distribution_lookup() -> dict[tuple[str, str], dict]:
    lookup: dict[tuple[str, str], dict] = {}
    for item in _load_catalog_distribution_entries():
        qualified_name = str(item.get("qualified_name") or item.get("name") or "").strip()
        version = str(item.get("version") or "").strip()
        if not qualified_name or not version:
            continue
        lookup[(qualified_name, version)] = item
    return lookup


def _snapshot_artifact_path(
    *,
    distribution: dict,
    field: str,
    fallbacks: list[str],
) -> str:
    candidate = str(distribution.get(field) or "").strip()
    if candidate:
        return candidate
    for fallback in fallbacks:
        value = str(fallback or "").strip()
        if value:
            return value
    return ""


def _catalog_snapshot_projections() -> list[DiscoveryProjection]:
    distribution_lookup = _snapshot_distribution_lookup()
    projections: list[DiscoveryProjection] = []
    for item in _load_catalog_snapshot_skill_entries():
        qualified_name = str(item.get("qualified_name") or item.get("name") or "").strip()
        version = str(item.get("latest_version") or item.get("default_install_version") or "").strip()
        if not qualified_name or not version:
            continue
        publisher, _, name = qualified_name.partition("/")
        if not publisher or not name:
            continue
        distribution = distribution_lookup.get((qualified_name, version), {})
        projections.append(
            DiscoveryProjection(
                exposure_id=0,
                release_id=0,
                audience_type="public",
                listing_mode=str(item.get("listing_mode") or "listed"),
                install_mode="enabled",
                review_requirement="none",
                exposure_state="active",
                release_state="ready",
                publisher=str(item.get("publisher") or publisher),
                kind=str(item.get("kind") or distribution.get("kind") or "skill"),
                name=name,
                qualified_name=qualified_name,
                display_name=str(item.get("display_name") or name),
                summary=str(item.get("summary") or distribution.get("summary") or ""),
                version=version,
                ready_at=None,
                manifest_path=_snapshot_artifact_path(
                    distribution=distribution,
                    field="manifest_path",
                    fallbacks=[
                        f"catalog/distributions/{publisher}/{name}/{version}/manifest.json",
                        f"skills/{publisher}/{name}/{version}/manifest.json",
                    ],
                ),
                bundle_path=_snapshot_artifact_path(
                    distribution=distribution,
                    field="bundle_path",
                    fallbacks=[
                        f"catalog/distributions/{publisher}/{name}/{version}/skill.tar.gz",
                        f"skills/{publisher}/{name}/{version}/skill.tar.gz",
                    ],
                ),
                provenance_path=_snapshot_artifact_path(
                    distribution=distribution,
                    field="attestation_path",
                    fallbacks=[
                        f"catalog/provenance/{name}-{version}.json",
                        f"provenance/{name}-{version}.json",
                        f"provenance/{publisher}--{name}-{version}.json",
                    ],
                ),
                signature_path=_snapshot_artifact_path(
                    distribution=distribution,
                    field="attestation_signature_path",
                    fallbacks=[
                        f"catalog/provenance/{name}-{version}.json.ssig",
                        f"provenance/{name}-{version}.json.ssig",
                        f"provenance/{publisher}--{name}-{version}.json.ssig",
                    ],
                ),
                bundle_sha256=(
                    str(distribution.get("bundle_sha256") or "").strip() or None
                ),
                supported_memory_modes=item.get("supported_memory_modes")
                if isinstance(item.get("supported_memory_modes"), list)
                else None,
                default_memory_mode=(
                    str(item.get("default_memory_mode") or "").strip() or None
                ),
            )
        )
    return projections


def _available_release_projections(db: Session) -> list[DiscoveryProjection]:
    settings = get_settings()
    artifact_root = settings.artifact_path
    repo_root = settings.repo_path
    entries = [
        entry
        for entry in build_release_projections(db)
        if projection_has_materialized_artifacts(entry, artifact_root, repo_root)
    ]
    return entries[:_CATALOG_MAX_ENTRIES]


def list_public_catalog(db: Session) -> list[DiscoveryProjection]:
    rows = [
        entry
        for entry in _available_release_projections(db)
        if entry.audience_type == "public" and entry.listing_mode == "listed"
    ]
    return _dedupe(rows)


def list_me_catalog(db: Session, *, context: AccessContext) -> list[DiscoveryProjection]:
    _ensure_user_context(context)
    rows = [
        entry
        for entry in _available_release_projections(db)
        if can_access_release(db, context=context, release_id=entry.release_id)
    ]
    return _dedupe(rows)


def list_grant_catalog(db: Session, *, context: AccessContext) -> list[DiscoveryProjection]:
    _ensure_grant_context(context)
    rows = [
        entry
        for entry in _available_release_projections(db)
        if entry.audience_type == "grant"
        and context.credential.grant_id is not None
        and can_access_release(db, context=context, release_id=entry.release_id)
    ]
    return _dedupe(rows)


def search_public_catalog(db: Session, *, query: str, limit: int) -> list[DiscoveryProjection]:
    return search.search_entries(list_public_catalog(db), query=query, limit=limit)


def search_me_catalog(
    db: Session, *, context: AccessContext, query: str, limit: int
) -> list[DiscoveryProjection]:
    return search.search_entries(list_me_catalog(db, context=context), query=query, limit=limit)


def search_grant_catalog(
    db: Session, *, context: AccessContext, query: str, limit: int
) -> list[DiscoveryProjection]:
    return search.search_entries(list_grant_catalog(db, context=context), query=query, limit=limit)


def resolve_public_install(db: Session, *, skill_ref: str) -> DiscoveryProjection:
    rows = [
        entry for entry in _available_release_projections(db) if entry.audience_type == "public"
    ]
    try:
        return _resolve_install_candidate(rows, skill_ref)
    except NotFoundError:
        snapshot_rows = _catalog_snapshot_projections()
        if not snapshot_rows:
            raise
        return _resolve_install_candidate(snapshot_rows, skill_ref)


def resolve_me_install(
    db: Session, *, context: AccessContext, skill_ref: str
) -> DiscoveryProjection:
    _ensure_user_context(context)
    all_rows = _available_release_projections(db)
    matches = _filter_install_candidates(all_rows, skill_ref)
    if not matches:
        raise NotFoundError("install target not found")
    rows = [
        entry
        for entry in matches
        if can_access_release(db, context=context, release_id=entry.release_id)
    ]
    if not rows:
        raise ForbiddenError("release access denied")
    return _resolve_install_candidate(rows, skill_ref)


def resolve_grant_install(
    db: Session, *, context: AccessContext, skill_ref: str
) -> DiscoveryProjection:
    _ensure_grant_context(context)
    all_rows = [
        entry for entry in _available_release_projections(db) if entry.audience_type == "grant"
    ]
    matches = _filter_install_candidates(all_rows, skill_ref)
    if not matches:
        raise NotFoundError("install target not found")
    rows = [
        entry
        for entry in matches
        if can_access_release(db, context=context, release_id=entry.release_id)
    ]
    if not rows:
        raise ForbiddenError("release access denied")
    return _resolve_install_candidate(rows, skill_ref)


def artifact_relative_path(entry: DiscoveryProjection, *, artifact: str) -> str:
    if artifact == "manifest":
        return entry.manifest_path
    if artifact == "bundle":
        return entry.bundle_path
    if artifact == "provenance":
        return entry.provenance_path
    if artifact == "signature":
        return entry.signature_path
    raise NotFoundError("artifact kind not found")
